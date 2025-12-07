# ---------------------------
# CONFIG
# ---------------------------
LOG_FILE = "logs.json"
MUTE_ROLE_NAME = "Muted"

# ---------------------------
# LOAD OR CREATE JSON
# ---------------------------
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w") as f:
        json.dump({}, f, indent=4)

def load_logs():
    with open(LOG_FILE, "r") as f:
        return json.load(f)

def save_logs(data):
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_log_channel(guild: discord.Guild):
    data = load_logs()
    gid = str(guild.id)
    if gid not in data:
        return None
    channel_id = data[gid].get("log_channel")
    return guild.get_channel(channel_id)

# ---------------------------
# BOT INIT
# ---------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------
# LOG CHANNEL COMMAND
# ---------------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def logs(ctx, channel: discord.TextChannel):
    data = load_logs()
    data[str(ctx.guild.id)] = {"log_channel": channel.id}
    save_logs(data)
    await ctx.send(f"Log channel set to {channel.mention}")

# ---------------------------
# HELPERS
# ---------------------------
async def get_audit_executor(guild, action, target_id=None, delay=1.0):
    await asyncio.sleep(delay)
    try:
        async for entry in guild.audit_logs(limit=10, action=action):
            if target_id is None or (entry.target and entry.target.id == target_id):
                return entry.user
    except:
        pass
    return None

def safe_mention(obj):
    if obj is None:
        return "Unknown"
    try:
        return obj.mention
    except:
        return str(obj)

# ---------------------------
# MESSAGE DELETE
# ---------------------------
@bot.event
async def on_message_delete(message):
    if not message.guild or message.author.bot:
        return

    channel = get_log_channel(message.guild)
    if not channel:
        return

    embed = discord.Embed(title="Message Deleted", color=0xFF0000)
    embed.add_field(name="User:", value=message.author.mention)
    embed.add_field(name="Content:", value=message.content or "[no text]", inline=False)
    embed.set_footer(text=f"User ID: {message.author.id}")
    await channel.send(embed=embed)

# ---------------------------
# MESSAGE EDIT
# ---------------------------
@bot.event
async def on_message_edit(before, after):
    if not before.guild or before.author.bot:
        return

    if before.content == after.content:
        return

    channel = get_log_channel(before.guild)
    if not channel:
        return

    embed = discord.Embed(title="Message Edited", color=0xFFFF00)
    embed.add_field(name="User:", value=before.author.mention)
    embed.add_field(name="Before:", value=before.content or "[no text]", inline=False)
    embed.add_field(name="After:", value=after.content or "[no text]", inline=False)
    embed.set_footer(text=f"User ID: {before.author.id}")
    await channel.send(embed=embed)

# ---------------------------
# BAN
# ---------------------------
@bot.event
async def on_member_ban(guild, user):
    channel = get_log_channel(guild)
    if not channel:
        return

    executor = await get_audit_executor(guild, AuditLogAction.ban, target_id=user.id)
    exec_text = safe_mention(executor)

    embed = discord.Embed(title="User Banned", color=0x990000)
    embed.add_field(name="User:", value=str(user))
    embed.add_field(name="Executor:", value=exec_text)
    embed.add_field(name="Ban Duration:", value="Permanent")
    embed.set_footer(text=f"User ID: {user.id}")
    await channel.send(embed=embed)

# ---------------------------
# UNBAN
# ---------------------------
@bot.event
async def on_member_unban(guild, user):
    channel = get_log_channel(guild)
    if not channel:
        return

    executor = await get_audit_executor(guild, AuditLogAction.unban, target_id=user.id)
    exec_text = safe_mention(executor)

    embed = discord.Embed(title="User Unbanned", color=0x00BB00)
    embed.add_field(name="User:", value=str(user))
    embed.add_field(name="Executor:", value=exec_text)
    embed.set_footer(text=f"User ID: {user.id}")
    await channel.send(embed=embed)

# ---------------------------
# MEMBER UPDATE (nickname, roles, mute/unmute)
# ---------------------------
@bot.event
async def on_member_update(before, after):
    guild = before.guild
    if not guild:
        return

    channel = get_log_channel(guild)
    if not channel:
        return

    # Executor fetcher
    async def fetch_exec(action):
        return safe_mention(await get_audit_executor(guild, action, target_id=after.id))

    # -----------------------
    # Nickname changed
    # -----------------------
    if before.nick != after.nick:
        executor = await fetch_exec(AuditLogAction.member_update)

        embed = discord.Embed(title="Nickname Changed", color=0x7289DA)
        embed.add_field(name="User:", value=after.mention)
        embed.add_field(name="Executor:", value=executor)
        embed.add_field(name="Before:", value=before.nick or before.name, inline=False)
        embed.add_field(name="After:", value=after.nick or after.name, inline=False)
        embed.set_footer(text=f"User ID: {after.id}")
        await channel.send(embed=embed)

    # -----------------------
    # Roles added
    # -----------------------
    added = [r for r in after.roles if r not in before.roles]
    if added:
        role = added[0]
        executor = await fetch_exec(AuditLogAction.member_role_update)

        embed = discord.Embed(title="Role Add", color=0x00AAFF)
        embed.add_field(name="User:", value=after.mention)
        embed.add_field(name="Executor:", value=executor)
        embed.add_field(name="Role Added:", value=role.mention)
        embed.set_footer(text=f"Role ID: {role.id} • User ID: {after.id}")
        await channel.send(embed=embed)

    # -----------------------
    # Roles removed
    # -----------------------
    removed = [r for r in before.roles if r not in after.roles]
    if removed:
        role = removed[0]
        executor = await fetch_exec(AuditLogAction.member_role_update)

        embed = discord.Embed(title="Role Removed", color=0xFF3333)
        embed.add_field(name="User:", value=after.mention)
        embed.add_field(name="Executor:", value=executor)
        embed.add_field(name="Role Removed:", value=role.mention)
        embed.set_footer(text=f"Role ID: {role.id} • User ID: {after.id}")
        await channel.send(embed=embed)

    # -----------------------
    # Mute & Unmute (by role)
    # -----------------------
    mute_role = discord.utils.get(guild.roles, name=MUTE_ROLE_NAME)
    if mute_role:

        # MUTED
        if mute_role not in before.roles and mute_role in after.roles:
            executor = await fetch_exec(AuditLogAction.member_role_update)

            embed = discord.Embed(title="User Muted", color=0xFF6600)
            embed.add_field(name="User:", value=after.mention)
            embed.add_field(name="Executor:", value=executor)
            embed.add_field(name="Mute Duration:", value="Unknown")
            embed.set_footer(text=f"User ID: {after.id}")
            await channel.send(embed=embed)

        # UNMUTED
        if mute_role in before.roles and mute_role not in after.roles:
            executor = await fetch_exec(AuditLogAction.member_role_update)

            embed = discord.Embed(title="User Unmuted", color=0x33CC33)
            embed.add_field(name="User:", value=after.mention)
            embed.add_field(name="Executor:", value=executor)
            embed.set_footer(text=f"User ID: {after.id}")
            await channel.send(embed=embed)
