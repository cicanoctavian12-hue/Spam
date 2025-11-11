import discord
from discord.ext import commands, tasks
import os
import random
import asyncio
import json
import re
from datetime import datetime, timedelta
from keep_alive import keep_alive 

# Start keep-alive and load token from environment
keep_alive()
TOKEN = os.getenv("TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # optional: for command sync during testing
DB_PATH = "panels.json"
AUTOROLES_PATH = "autoroles.json"

if not TOKEN:
    print("ERROR: TOKEN environment variable not set. Exiting.")
    raise SystemExit(1)

# Intents - MEMBERS intent is required for on_member_join and role assignment
intents = discord.Intents.default()
intents.guilds = True
intents.members = True  # required to add/remove roles and receive member join events
intents.messages = True
intents.message_content = True
intents.reactions = True

# Accept both "!" and "?" prefixes so ?autorole will work
bot = commands.Bot(command_prefix=("!", "?"), intents=intents)
tree = bot.tree

# ---------------- Persistence helpers ----------------
def load_json_file(path, default):
    if not os.path.exists(path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f)
        except Exception:
            pass
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f)
        except Exception:
            pass
        return default

def save_json_file(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save {path}: {e}")

# load panels and autoroles on startup
panels = load_json_file(DB_PATH, [])
autoroles = load_json_file(AUTOROLES_PATH, {})  # {guild_id: role_id}

# ---------------- Emoji parsing ----------------
CUSTOM_EMOJI_RE = re.compile(r"^<(a?):([A-Za-z0-9_~]+):([0-9]+)>$")
NAME_ID_RE = re.compile(r"^([A-Za-z0-9_~]+):([0-9]+)$")

def parse_emoji_input(raw):
    if not raw:
        return None
    raw = raw.strip()
    m = CUSTOM_EMOJI_RE.match(raw)
    if m:
        animated_flag = True if m.group(1) == "a" else False
        try:
            return {"type": "custom", "id": int(m.group(3)), "name": m.group(2), "animated": animated_flag}
        except ValueError:
            return None
    m2 = NAME_ID_RE.match(raw)
    if m2:
        try:
            return {"type": "custom", "id": int(m2.group(2)), "name": m2.group(1), "animated": False}
        except ValueError:
            return None
    # fallback: unicode or raw string
    return {"type": "unicode", "name": raw}

# ---------------- Color parsing for /embed ----------------
COLOR_MAP = {
    "red": 0xFF0000,
    "blue": 0x0000FF,
    "green": 0x00FF00,
    "yellow": 0xFFFF00,
    "orange": 0xFFA500,
    "purple": 0x800080,
    "pink": 0xFFC0CB,
    "black": 0x000000,
    "white": 0xFFFFFF,
    "grey": 0x808080,
    "gray": 0x808080,
    "teal": 0x008080,
    "gold": 0xFFD700,
    "default": 0x00AE86
}

def parse_color(value: str) -> int:
    if not value:
        raise ValueError("No color provided")
    v = value.strip().lower()
    if v in COLOR_MAP:
        return COLOR_MAP[v]
    if v.startswith("#"):
        v = v[1:]
    if v.startswith("0x"):
        v = v[2:]
    if re.fullmatch(r"[0-9a-f]{6}", v):
        return int(v, 16)
    if v.isdigit():
        iv = int(v)
        if 0 <= iv <= 0xFFFFFF:
            return iv
    raise ValueError("Invalid color format. Use a color name (red) or hex (#ff0000).")

# ---------------- Ready & sync ----------------
@bot.event
async def on_ready():
    global panels, autoroles
    panels = load_json_file(DB_PATH, [])
    autoroles = load_json_file(AUTOROLES_PATH, {})
    print(f"Logged in as {bot.user} (id: {bot.user.id}). Loaded {len(panels)} panel(s) and {len(autoroles)} autorole(s).")
    try:
        if GUILD_ID:
            guild_obj = discord.Object(id=int(GUILD_ID))
            await tree.sync(guild=guild_obj)
            print(f"Synced commands to guild {GUILD_ID}.")
        else:
            await tree.sync()
            print("Synced global commands (may take up to an hour to appear).")
    except Exception as e:
        print("Failed to sync commands:", e)

# ---------------- Autorole assignment helpers ----------------
async def _assign_auto_role(member: discord.Member, role_id: int):
    guild = member.guild
    role = guild.get_role(int(role_id))
    if role is None:
        print(f"[auto-role] Role id {role_id} not found in guild {guild.id}.")
        # notify owner best-effort
        try:
            owner = guild.owner
            if owner:
                await owner.send(f"I tried to auto-assign role id `{role_id}` in **{guild.name}** but that role doesn't exist.")
        except Exception:
            pass
        return

    try:
        bot_member = guild.get_member(bot.user.id) or await guild.fetch_member(bot.user.id)
    except Exception:
        bot_member = None

    if bot_member is None:
        print(f"[auto-role] Could not fetch bot member in guild {guild.id}.")
        return

    if not bot_member.guild_permissions.manage_roles:
        print(f"[auto-role] Bot lacks Manage Roles in guild {guild.id}. Cannot assign role.")
        try:
            owner = guild.owner
            if owner:
                await owner.send(f"I tried to auto-assign the role `{role.name}` in **{guild.name}** but I don't have Manage Roles permission.")
        except Exception:
            pass
        return

    bot_top = bot_member.top_role
    if bot_top.position <= role.position:
        print(f"[auto-role] Bot top role {bot_top.name} (pos {bot_top.position}) is not higher than target role {role.name} (pos {role.position}). Cannot assign.")
        try:
            owner = guild.owner
            if owner:
                await owner.send(
                    f"I attempted to auto-assign the role `{role.name}` in **{guild.name}**, but my top role (`{bot_top.name}`) is not higher than `{role.name}`.\n"
                    "Please move my role above the role you want me to assign and ensure I have Manage Roles permission."
                )
        except Exception:
            pass
        return

    try:
        await member.add_roles(role, reason="Auto role on join")
        print(f"[auto-role] Assigned role {role.name} ({role.id}) to {member} on join in guild {guild.id}.")
        try:
            if guild.system_channel and guild.system_channel.permissions_for(bot_member).send_messages:
                await guild.system_channel.send(f"Welcome {member.mention}! You were given the {role.mention} role.")
        except Exception:
            pass
    except discord.Forbidden as exc:
        print(f"[auto-role] Forbidden error assigning role {role.id} to {member.id}: {exc}")
        try:
            owner = guild.owner
            if owner:
                await owner.send(f"I was forbidden from assigning `{role.name}` to {member.mention} in **{guild.name}**. Please check my permissions and role position.")
        except Exception:
            pass
    except Exception as exc:
        print(f"[auto-role] Error assigning role {role.id} to {member.id}: {exc}. Retrying in 1s.")
        await asyncio.sleep(1)
        try:
            await member.add_roles(role, reason="Auto role on join (retry)")
            print(f"[auto-role] Assigned role {role.name} ({role.id}) to {member} on retry.")
        except Exception as e2:
            print(f"[auto-role] Retry failed assigning role {role.id} to {member.id}: {e2}")
            try:
                owner = guild.owner
                if owner:
                    await owner.send(f"I failed to auto-assign `{role.name}` to {member.mention} in **{guild.name}**. Error: {e2}")
            except Exception:
                pass

@bot.event
async def on_member_join(member: discord.Member):
    """
    Auto-assign the configured role (if any) for the guild when a member joins.
    Uses the persisted 'autoroles' mapping.
    """
    await bot.wait_until_ready()
    guild_id = str(member.guild.id)
    role_id = autoroles.get(guild_id)
    if role_id:
        # run in background so join processing isn't blocked
        asyncio.create_task(_assign_auto_role(member, int(role_id)))

# ---------------- Reaction handlers (raw events) ----------------
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return
    try:
        if payload.guild_id is None:
            return
        panel = next((p for p in panels if p.get("message_id") == str(payload.message_id) and p.get("guild_id") == str(payload.guild_id)), None)
        if not panel:
            return

        emoji_id = payload.emoji.id
        emoji_name = payload.emoji.name
        matched = None
        for e in panel.get("entries", []):
            if e.get("type") == "custom":
                try:
                    if emoji_id is not None and int(e.get("id")) == int(emoji_id):
                        matched = e
                        break
                    if emoji_name and str(e.get("name")) == str(emoji_name):
                        matched = e
                        break
                except Exception:
                    continue
            else:
                if emoji_id is None and e.get("name") == emoji_name:
                    matched = e
                    break
        if not matched:
            return

        guild = bot.get_guild(payload.guild_id) or await bot.fetch_guild(payload.guild_id)
        try:
            member = await guild.fetch_member(payload.user_id)
        except Exception:
            member = guild.get_member(payload.user_id)
        if not member:
            return

        role_id = int(matched.get("role_id"))
        role = guild.get_role(role_id)
        if not role:
            print(f"[reaction_add] Role id {role_id} not found in guild {guild.id}.")
            return

        if role.id not in [r.id for r in member.roles]:
            try:
                await member.add_roles(role, reason=f"Reaction role (message {panel['message_id']})")
                print(f"[reaction_add] Added role {role.name} ({role.id}) to {member} for reaction on message {panel['message_id']}.")
            except Exception as e:
                print(f"[reaction_add] Failed to add role {role_id} to {member.id}:", e)
    except Exception as e:
        print("Error in on_raw_reaction_add:", e)

@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return
    try:
        if payload.guild_id is None:
            return
        panel = next((p for p in panels if p.get("message_id") == str(payload.message_id) and p.get("guild_id") == str(payload.guild_id)), None)
        if not panel:
            return

        emoji_id = payload.emoji.id
        emoji_name = payload.emoji.name
        matched = None
        for e in panel.get("entries", []):
            if e.get("type") == "custom":
                try:
                    if emoji_id is not None and int(e.get("id")) == int(emoji_id):
                        matched = e
                        break
                    if emoji_name and str(e.get("name")) == str(emoji_name):
                        matched = e
                        break
                except Exception:
                    continue
            else:
                if emoji_id is None and e.get("name") == emoji_name:
                    matched = e
                    break
        if not matched:
            return

        guild = bot.get_guild(payload.guild_id) or await bot.fetch_guild(payload.guild_id)
        try:
            member = await guild.fetch_member(payload.user_id)
        except Exception:
            member = guild.get_member(payload.user_id)
        if not member:
            return

        role_id = int(matched.get("role_id"))
        role = guild.get_role(role_id)
        if not role:
            print(f"[reaction_remove] Role id {role_id} not found in guild {guild.id}.")
            return

        if role.id in [r.id for r in member.roles]:
            try:
                await member.remove_roles(role, reason=f"Reaction role removal (message {panel['message_id']})")
                print(f"[reaction_remove] Removed role {role.name} ({role.id}) from {member} for reaction remove on message {panel['message_id']}.")
            except Exception as e:
                print(f"[reaction_remove] Failed to remove role {role_id} from {member.id}:", e)
    except Exception as e:
        print("Error in on_raw_reaction_remove:", e)

# ---------------- /role-panel command (unchanged) ----------------
@bot.tree.command(name="role-panel", description="Create a reaction role panel (up to 5 emoji↔role pairs).")
@discord.app_commands.describe(
    text="Text to show in the embed",
    emoji1="Emoji 1 (unicode or <:name:id>) - required",
    role1="Role for emoji1 - required",
    emoji2="Emoji 2 (optional)",
    role2="Role 2 (optional)",
    emoji3="Emoji 3 (optional)",
    role3="Role 3 (optional)",
    emoji4="Emoji 4 (optional)",
    role4="Role 4 (optional)",
    emoji5="Emoji 5 (optional)",
    role5="Role 5 (optional)",
)
async def role_panel(
    interaction: discord.Interaction,
    text: str,
    emoji1: str,
    role1: discord.Role,
    emoji2: str = None,
    role2: discord.Role = None,
    emoji3: str = None,
    role3: discord.Role = None,
    emoji4: str = None,
    role4: discord.Role = None,
    emoji5: str = None,
    role5: discord.Role = None,
):
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("You need the Manage Roles permission to create a role panel.", ephemeral=True)
        return

    raw_pairs = [
        (emoji1, role1),
        (emoji2, role2),
        (emoji3, role3),
        (emoji4, role4),
        (emoji5, role5),
    ]
    pairs = []
    for idx, (e_raw, r) in enumerate(raw_pairs, start=1):
        if e_raw and r:
            parsed = parse_emoji_input(e_raw)
            if not parsed:
                await interaction.response.send_message(f"Invalid emoji format for emoji{idx}: {e_raw}", ephemeral=True)
                return
            pairs.append((parsed, r))
        elif (e_raw and not r) or (r and not e_raw):
            await interaction.response.send_message(f"Both emoji{idx} and role{idx} must be provided together.", ephemeral=True)
            return

    if len(pairs) == 0:
        await interaction.response.send_message("You must provide at least emoji1 and role1.", ephemeral=True)
        return

    embed = discord.Embed(description=text, color=0x00AE86)
    if interaction.guild and interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)

    lines = []
    for parsed, role in pairs:
        if parsed["type"] == "custom":
            lines.append(f"<:{parsed['name']}:{parsed['id']}> — {role.mention}")
        else:
            lines.append(f"{parsed['name']} — {role.mention}")
    embed.add_field(name="Reactions", value="\n".join(lines), inline=False)

    await interaction.response.defer(ephemeral=False)
    channel = interaction.channel
    try:
        sent = await channel.send(embed=embed)
    except Exception as exc:
        print("Failed to send panel message:", exc)
        await interaction.followup.send("Failed to send the panel message in this channel.", ephemeral=True)
        return

    for parsed, role in pairs:
        try:
            if parsed["type"] == "custom":
                try:
                    p = discord.PartialEmoji(name=parsed["name"], id=int(parsed["id"]), animated=bool(parsed.get("animated", False)))
                    await sent.add_reaction(p)
                except Exception:
                    raw_str = f"<a:{parsed['name']}:{parsed['id']}>" if parsed.get("animated", False) else f"<:{parsed['name']}:{parsed['id']}>"
                    try:
                        await sent.add_reaction(raw_str)
                    except Exception:
                        print(f"Could not react with custom emoji {parsed['name']}:{parsed['id']}. Bot may not have access.")
            else:
                try:
                    await sent.add_reaction(parsed["name"])
                except Exception:
                    print(f"Failed to react with unicode/char {parsed['name']!r}.")
        except Exception as e:
            print("Unexpected error while reacting:", e)

    entry = {
        "guild_id": str(interaction.guild.id),
        "channel_id": str(channel.id),
        "message_id": str(sent.id),
        "created_at": datetime.utcnow().isoformat(),
        "entries": []
    }
    for parsed, role in pairs:
        if parsed["type"] == "custom":
            entry["entries"].append({
                "type": "custom",
                "id": int(parsed["id"]),
                "name": parsed["name"],
                "animated": bool(parsed.get("animated", False)),
                "role_id": str(role.id)
            })
        else:
            entry["entries"].append({
                "type": "unicode",
                "name": parsed["name"],
                "role_id": str(role.id)
            })

    panels.append(entry)
    save_json_file(DB_PATH, panels)
    await interaction.followup.send("Role panel created.", ephemeral=True)

# ---------------- /embed command (updated) ----------------
@bot.tree.command(name="embed", description="Create an embed by typing the message after the command. Options: channel (required), color (required), picture (optional).")
@discord.app_commands.describe(
    channel="Channel where the embed will be sent (required)",
    color="Color name (blue, red) or hex code (#ff0000) (required)",
    picture="Optional direct image URL to show under the embed"
)
async def create_embed(interaction: discord.Interaction, channel: discord.TextChannel, color: str, picture: str = None):
    if not interaction.user.guild_permissions.send_messages and not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    if picture:
        picture = picture.strip()
        if not (picture.startswith("http://") or picture.startswith("https://")):
            await interaction.response.send_message("Picture must be a valid URL starting with http:// or https://", ephemeral=True)
            return

    try:
        color_int = parse_color(color)
    except ValueError as e:
        await interaction.response.send_message(f"Invalid color: {e}", ephemeral=True)
        return

    await interaction.response.send_message("What message you want to be in embed? (The first message you send here will be used)", ephemeral=True)

    def check(m: discord.Message):
        return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

    try:
        msg = await bot.wait_for('message', timeout=180.0, check=check)
    except asyncio.TimeoutError:
        await interaction.followup.send("Timed out waiting for your message. Please run the command again.", ephemeral=True)
        return

    content = msg.content
    if not content or content.strip() == "":
        await interaction.followup.send("Empty message received. Aborting.", ephemeral=True)
        return

    embed = discord.Embed(description=content, color=color_int)
    if picture:
        embed.set_image(url=picture)

    try:
        await channel.send(embed=embed)
        await interaction.followup.send(f"Embed sent to {channel.mention}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("I don't have permission to send messages or embeds in the target channel.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Failed to send embed: {e}", ephemeral=True)

# ---------------- ?autorole command (message command) ----------------
@bot.command(name="autorole")
@commands.has_guild_permissions(manage_guild=True)
async def autorole_cmd(ctx, *, role_input: str = None):
    """
    Usage:
      ?autorole @Role        -> sets autorole to @Role
      ?autorole off|remove   -> disables autorole
      ?autorole              -> shows current autorole setting
    Requires Manage Server permission.
    """
    guild_id = str(ctx.guild.id)
    if role_input is None:
        current = autoroles.get(guild_id)
        if current:
            role = ctx.guild.get_role(int(current))
            if role:
                await ctx.send(f"Current autorole for this server is {role.mention} ({role.id}).")
            else:
                await ctx.send(f"Configured autorole id `{current}` not found in this server. Use `?autorole @role` to set it.")
        else:
            await ctx.send("No autorole is configured for this server. Use `?autorole @role` to set one.")
        return

    arg = role_input.strip().lower()
    if arg in ("off", "remove", "none", "disable"):
        if guild_id in autoroles:
            del autoroles[guild_id]
            save_json_file(AUTOROLES_PATH, autoroles)
            await ctx.send("Autorole disabled for this server.")
        else:
            await ctx.send("Autorole is not configured for this server.")
        return

    # Try to resolve a role mention / name / id
    role = None
    # If user mentioned role, discord will present it in message.role_mentions
    if ctx.message.role_mentions:
        role = ctx.message.role_mentions[0]
    else:
        # try by id
        cleaned = re.sub(r"[<@&> ]", "", role_input)
        if cleaned.isdigit():
            role = ctx.guild.get_role(int(cleaned))
        if role is None:
            # try by name (case-insensitive)
            role = discord.utils.get(ctx.guild.roles, name=role_input) or discord.utils.get(ctx.guild.roles, name=role_input.strip())

    if role is None:
        await ctx.send("Could not find that role. Mention the role (like @Role) or provide role ID or exact role name.")
        return

    # Save mapping
    autoroles[guild_id] = str(role.id)
    save_json_file(AUTOROLES_PATH, autoroles)
    await ctx.send(f"Autorole set to {role.mention}. New members will receive this role when they join.")

# Handle missing permission error for autorole command
@autorole_cmd.error
async def autorole_cmd_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need the Manage Server permission to configure autorole.")
    else:
        await ctx.send(f"Error: {error}")

# ---------------- Admin helper to test autorole ----------------
@bot.command(name="autorole-test")
@commands.has_guild_permissions(manage_guild=True)
async def autorole_test_cmd(ctx, member: discord.Member = None):
    """Manual test: attempt to assign configured autorole to a member right now."""
    if member is None:
        member = ctx.author
    guild_id = str(ctx.guild.id)
    role_id = autoroles.get(guild_id)
    if not role_id:
        await ctx.send("No autorole configured for this server.")
        return
    await ctx.send(f"Attempting to assign autorole to {member.mention}...")
    await _assign_auto_role(member, int(role_id))
    await ctx.send("Done (check member roles / logs).")

@autorole_test_cmd.error
async def autorole_test_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need the Manage Server permission to use this.")
    else:
        await ctx.send(f"Error: {error}")

# ---------------- Run ----------------
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("Shutdown requested by user.")
    except Exception as e:
        print("Error starting bot:", e)