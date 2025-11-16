import os
import re
import json
import asyncio
import random
from datetime import datetime
from typing import Optional, List, Dict, Any

import discord
from discord import app_commands
from discord.ext import commands
from keep_alive import keep_alive

# ---------------- Startup & config ----------------
keep_alive()
TOKEN = os.getenv("TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # optional: for quick guild-only command sync
DB_PATH = "panels.json"
AUTOROLES_PATH = "autoroles.json"

if not TOKEN:
    print("ERROR: TOKEN environment variable not set. Exiting.")
    raise SystemExit(1)

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True
intents.reactions = True

# Accept both "!" and "?" for legacy commands
bot = commands.Bot(command_prefix=("!", "?"), intents=intents)
tree = bot.tree

# ---------------- Persistence helpers ----------------
def load_json_file(path: str, default):
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

def save_json_file(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save {path}: {e}")

panels: List[Dict[str, Any]] = load_json_file(DB_PATH, [])
autoroles: Dict[str, str] = load_json_file(AUTOROLES_PATH, {})

# ---------------- Utilities ----------------
CUSTOM_EMOJI_RE = re.compile(r"^<(a?):([A-Za-z0-9_~]+):([0-9]+)>$")
NAME_ID_RE = re.compile(r"^([A-Za-z0-9_~]+):([0-9]+)$")

def parse_emoji_input(raw: str):
    if not raw:
        return None
    raw = raw.strip()
    m = CUSTOM_EMOJI_RE.match(raw)
    if m:
        animated_flag = m.group(1) == "a"
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
    return {"type": "unicode", "name": raw}

def is_valid_url(u: str) -> bool:
    return isinstance(u, str) and (u.startswith("http://") or u.startswith("https://"))

# ---------------- Startup sync ----------------
@bot.event
async def on_ready():
    global panels, autoroles
    panels = load_json_file(DB_PATH, [])
    autoroles = load_json_file(AUTOROLES_PATH, {})
    
    await bot.change_presence(activity=discord.CustomActivity(name="⛄• Stumble Hour"))
    
    bot.add_view(CCApplyButtonView())
    bot.add_view(CCApplicationReviewView())
    
    print(f"Logged in as {bot.user} (id: {bot.user.id}). Loaded {len(panels)} panels and {len(autoroles)} autoroles.")
    try:
        if GUILD_ID:
            guild_obj = discord.Object(id=int(GUILD_ID))
            await tree.sync(guild=guild_obj)
            print(f"Synced commands to guild {GUILD_ID}.")
        else:
            await tree.sync()
            print("Synced global commands.")
    except Exception as e:
        print("Failed to sync commands:", e)

# ---------------- Autorole system (unchanged) ----------------
async def _assign_auto_role(member: discord.Member, role_id: int):
    guild = member.guild
    role = guild.get_role(int(role_id))
    if role is None:
        print(f"[auto-role] role {role_id} not found in guild {guild.id}")
        return
    try:
        bot_member = guild.get_member(bot.user.id) or await guild.fetch_member(bot.user.id)
    except Exception:
        bot_member = None
    if bot_member is None or not bot_member.guild_permissions.manage_roles:
        print(f"[auto-role] bot lacks manage_roles in guild {guild.id}")
        return
    bot_top = bot_member.top_role
    if bot_top.position <= role.position:
        print(f"[auto-role] hierarchy issue: bot top pos {bot_top.position} <= role pos {role.position}")
        return
    try:
        await member.add_roles(role, reason="Auto role on join")
        print(f"[auto-role] assigned {role.id} to {member.id} in {guild.id}")
    except Exception as e:
        print(f"[auto-role] failed to add role {role.id} to {member.id}: {e}")

@bot.event
async def on_member_join(member: discord.Member):
    await bot.wait_until_ready()
    gid = str(member.guild.id)
    rid = autoroles.get(gid)
    if rid:
        asyncio.create_task(_assign_auto_role(member, int(rid)))

@bot.command(name="autorole")
@commands.has_guild_permissions(manage_guild=True)
async def autorole_cmd(ctx, *, role_input: str = None):
    gid = str(ctx.guild.id)
    if role_input is None:
        current = autoroles.get(gid)
        if current:
            role = ctx.guild.get_role(int(current))
            if role:
                await ctx.send(f"Current autorole: {role.mention} ({role.id})")
            else:
                await ctx.send(f"Configured autorole id {current} not found. Use `?autorole @role` to set.")
        else:
            await ctx.send("No autorole configured. Use `?autorole @role` to set.")
        return
    arg = role_input.strip().lower()
    if arg in ("off", "remove", "none", "disable"):
        if gid in autoroles:
            del autoroles[gid]
            save_json_file(AUTOROLES_PATH, autoroles)
            await ctx.send("Autorole disabled.")
        else:
            await ctx.send("Autorole wasn't configured.")
        return
    role = None
    if ctx.message.role_mentions:
        role = ctx.message.role_mentions[0]
    else:
        cleaned = re.sub(r"[<@&> ]", "", role_input)
        if cleaned.isdigit():
            role = ctx.guild.get_role(int(cleaned))
        if role is None:
            role = discord.utils.get(ctx.guild.roles, name=role_input) or discord.utils.get(ctx.guild.roles, name=role_input.strip())
    if role is None:
        await ctx.send("Could not find that role. Mention it or provide ID/name.")
        return
    autoroles[gid] = str(role.id)
    save_json_file(AUTOROLES_PATH, autoroles)
    await ctx.send(f"Autorole set to {role.mention}.")

# ---------------- Lock / Unlock commands (updated) ----------------
SUCCESS_EMOJI = "<:SCSuccess:1439236476616310844>"
GREEN_COLOR = 0x2ECC71  # pleasant green

@bot.command(name="lock")
@commands.has_guild_permissions(manage_channels=True)
async def lock(ctx):
    """
    Usage:
      !lock
    Denies send_messages to @everyone and posts a persistent green embed confirming the lock.
    """
    try:
        # Attempt to delete invoking command message for cleanliness (best-effort)
        try:
            await ctx.message.delete()
        except Exception:
            pass

        channel = ctx.channel
        guild = ctx.guild
        everyone = guild.default_role

        # Preserve read_messages permission if set for @everyone
        current_overwrite = channel.overwrites_for(everyone)
        read_perm = current_overwrite.read_messages if current_overwrite.read_messages is not None else True

        # Deny send_messages for @everyone
        await channel.set_permissions(everyone, send_messages=False, read_messages=read_perm)

        # Send persistent green embed confirmation (does not auto-delete)
        embed = discord.Embed(title=None, description=f"{SUCCESS_EMOJI} Channel successfully locked!", color=GREEN_COLOR)
        await channel.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to change channel permissions. Ensure my role is high enough and I have Manage Roles.", delete_after=10)
    except Exception as e:
        await ctx.send(f"❌ An error occurred while locking the channel: {e}", delete_after=10)

@lock.error
async def lock_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need the Manage Channels permission to lock channels.", delete_after=8)
    else:
        await ctx.send(f"❌ Error: {error}", delete_after=8)

@bot.command(name="unlock")
@commands.has_guild_permissions(manage_channels=True)
async def unlock(ctx):
    """
    Usage:
      !unlock
    Clears explicit send_messages deny for @everyone and posts a persistent green embed confirming unlock.
    """
    try:
        try:
            await ctx.message.delete()
        except Exception:
            pass

        channel = ctx.channel
        everyone = ctx.guild.default_role

        # Fetch current overwrite for @everyone
        eo = channel.overwrites_for(everyone)
        if eo.send_messages is not None:
            eo.send_messages = None
            await channel.set_permissions(everyone, overwrite=eo)
        else:
            # even if none, we still proceed

            pass

        # Also clear send_messages explicit overwrites for any other targets (roles/members) to restore default behavior
        for target, overwrite in list(channel.overwrites.items()):
            if overwrite.send_messages is not None:
                # clear only send_messages while keeping other perms intact
                new_over = discord.PermissionOverwrite(
                    read_messages=overwrite.read_messages,
                    send_messages=None,
                    speak=overwrite.speak,
                    add_reactions=overwrite.add_reactions,
                    manage_messages=overwrite.manage_messages,
                    manage_channels=overwrite.manage_channels,
                    connect=overwrite.connect
                )
                await channel.set_permissions(target, overwrite=new_over)

        # Send persistent green embed confirmation
        embed = discord.Embed(title=None, description=f"{SUCCESS_EMOJI} Channel successfully unlocked!", color=GREEN_COLOR)
        await channel.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to change channel permissions. Ensure my role is high enough and I have Manage Roles.", delete_after=10)
    except Exception as e:
        await ctx.send(f"❌ An error occurred while unlocking the channel: {e}", delete_after=10)

@unlock.error
async def unlock_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need the Manage Channels permission to unlock channels.", delete_after=8)
    else:
        await ctx.send(f"❌ Error: {error}", delete_after=8)

# ---------------- Reaction-role panel (unchanged) ----------------
@tree.command(name="role-panel", description="Create a reaction role panel (up to 5 emoji↔role pairs).")
@app_commands.describe(
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
    emoji2: Optional[str] = None,
    role2: Optional[discord.Role] = None,
    emoji3: Optional[str] = None,
    role3: Optional[discord.Role] = None,
    emoji4: Optional[str] = None,
    role4: Optional[discord.Role] = None,
    emoji5: Optional[str] = None,
    role5: Optional[discord.Role] = None,
):
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("You need Manage Roles permission to create panels.", ephemeral=True)
        return
    raw_pairs = [(emoji1, role1), (emoji2, role2), (emoji3, role3), (emoji4, role4), (emoji5, role5)]
    pairs = []
    for idx, (e_raw, r) in enumerate(raw_pairs, start=1):
        if e_raw and r:
            parsed = parse_emoji_input(e_raw)
            if not parsed:
                await interaction.response.send_message(f"Invalid emoji for emoji{idx}: {e_raw}", ephemeral=True)
                return
            pairs.append((parsed, r))
        elif (e_raw and not r) or (r and not e_raw):
            await interaction.response.send_message(f"Both emoji{idx} and role{idx} must be provided", ephemeral=True)
            return
    if len(pairs) == 0:
        await interaction.response.send_message("At least emoji1 and role1 required.", ephemeral=True)
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
    await interaction.response.defer()
    channel = interaction.channel
    try:
        sent = await channel.send(embed=embed)
    except Exception as e:
        await interaction.followup.send("Failed to send panel message.", ephemeral=True)
        print("panel send failed:", e)
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
                        print("Could not react with custom emoji", parsed)
            else:
                await sent.add_reaction(parsed["name"])
        except Exception:
            pass
    entry = {"guild_id": str(interaction.guild.id), "channel_id": str(channel.id), "message_id": str(sent.id), "created_at": datetime.utcnow().isoformat(), "entries": []}
    for parsed, role in pairs:
        if parsed["type"] == "custom":
            entry["entries"].append({"type": "custom", "id": int(parsed["id"]), "name": parsed["name"], "animated": bool(parsed.get("animated", False)), "role_id": str(role.id)})
        else:
            entry["entries"].append({"type": "unicode", "name": parsed["name"], "role_id": str(role.id)})
    panels.append(entry)
    save_json_file(DB_PATH, panels)
    await interaction.followup.send("Role panel created.", ephemeral=True)

# ---------------- Reaction add/remove handlers (unchanged) ----------------
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
                        matched = e; break
                    if emoji_name and str(e.get("name")) == str(emoji_name):
                        matched = e; break
                except Exception:
                    continue
            else:
                if emoji_id is None and e.get("name") == emoji_name:
                    matched = e; break
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
            print("role not found", role_id)
            return
        if role.id not in [r.id for r in member.roles]:
            try:
                await member.add_roles(role, reason=f"Reaction role (message {panel['message_id']})")
            except Exception as e:
                print("failed to add role:", e)
    except Exception as e:
        print("on_raw_reaction_add error:", e)

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
                        matched = e; break
                    if emoji_name and str(e.get("name")) == str(emoji_name):
                        matched = e; break
                except Exception:
                    continue
            else:
                if emoji_id is None and e.get("name") == emoji_name:
                    matched = e; break
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
            print("role not found", role_id)
            return
        if role.id in [r.id for r in member.roles]:
            try:
                await member.remove_roles(role, reason=f"Reaction role removal (message {panel['message_id']})")
            except Exception as e:
                print("failed to remove role:", e)
    except Exception as e:
        print("on_raw_reaction_remove error:", e)

# ---------------- Content Creator Application System ----------------
ADMIN_CHANNEL_ID = 1439265373697605683

COLOR_MAP = {
    "blue": 0x3498DB,
    "red": 0xE74C3C,
    "yellow": 0xF1C40F,
    "green": 0x2ECC71,
    "purple": 0x9B59B6,
    "orange": 0xE67E22,
    "pink": 0xF368E0,
    "black": 0x2C3E50,
    "white": 0xECF0F1,
}

class CCApplicationModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Content Creator Application")
    question1 = discord.ui.TextInput(
        label="What is your discord username?",
        style=discord.TextStyle.short,
        required=True,
        max_length=500
    )
    
    question2 = discord.ui.TextInput(
        label="On which Platform do you Post Videos?",
        style=discord.TextStyle.short,
        required=True,
        max_length=500
    )
    
    question3 = discord.ui.TextInput(
        label="What content do you do?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )
    
    question4 = discord.ui.TextInput(
        label="What is your age?",
        style=discord.TextStyle.short,
        required=True,
        max_length=500
    )
    
    question5 = discord.ui.TextInput(
        label="Why do you want to be a Content Creator for Stumble Hour?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
            if not admin_channel:
                await interaction.response.send_message("Error: Admin channel not found.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="New Content Creator Application",
                color=0x9B59B6,
                timestamp=datetime.utcnow()
            )
            embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
            
            embed.add_field(
                name="Q1: What is your discord username?",
                value=f"A: {self.question1.value}",
                inline=False
            )
            embed.add_field(
                name="Q2: On which Platform do you Post Videos?",
                value=f"A: {self.question2.value}",
                inline=False
            )
            embed.add_field(
                name="Q3: What content do you do?",
                value=f"A: {self.question3.value}",
                inline=False
            )
            embed.add_field(
                name="Q4: What is your age?",
                value=f"A: {self.question4.value}",
                inline=False
            )
            embed.add_field(
                name="Q5: Why do you want to be a Content Creator for Stumble Hour?",
                value=f"A: {self.question5.value}",
                inline=False
            )
            
            view = CCApplicationReviewView(user_id=interaction.user.id)
            await admin_channel.send(embed=embed, view=view)
            
            await interaction.response.send_message("Your application has been submitted successfully!", ephemeral=True)
        except Exception as e:
            print(f"Error submitting application: {e}")
            await interaction.response.send_message("An error occurred while submitting your application.", ephemeral=True)

class CCApplyButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label=" Apply here",
        style=discord.ButtonStyle.primary,
        emoji="<:CreatorIcon:1439238460270444594>",
        custom_id="cc_apply:apply_button"
    )
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CCApplicationModal())

class CCApplicationReviewView(discord.ui.View):
    def __init__(self, user_id: int = None):
        super().__init__(timeout=None)
        self.user_id = user_id
    
    @discord.ui.button(
        label=" Accept",
        style=discord.ButtonStyle.success,
        emoji="<:SCSuccess:1439236476616310844>",
        custom_id="cc_review:accept"
    )
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = self.user_id
        if not user_id and interaction.message and interaction.message.embeds:
            try:
                embed = interaction.message.embeds[0]
                if embed.author and embed.author.name:
                    username = embed.author.name
                    user = discord.utils.get(interaction.guild.members, name=username)
                    if user:
                        user_id = user.id
            except Exception:
                pass
        
        if not user_id:
            await interaction.response.send_message("Error: Could not identify the applicant.", ephemeral=True)
            return
        
        try:
            user = await bot.fetch_user(user_id)
            await user.send("> <:SCSuccess:1439236476616310844> Your Content Creator application was accepted.")
            await interaction.response.send_message(f"Application accepted. {user.mention} has been notified.", ephemeral=True)
            
            if interaction.message:
                await interaction.message.edit(view=None)
        except discord.Forbidden:
            await interaction.response.send_message(f"Could not DM user (ID: {user_id}). They may have DMs disabled.", ephemeral=True)
        except Exception as e:
            print(f"Error in accept button: {e}")
            await interaction.response.send_message("An error occurred.", ephemeral=True)
    
    @discord.ui.button(
        label=" Reject",
        style=discord.ButtonStyle.danger,
        emoji="<:Cross:1439266290601820212>",
        custom_id="cc_review:reject"
    )
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = self.user_id
        if not user_id and interaction.message and interaction.message.embeds:
            try:
                embed = interaction.message.embeds[0]
                if embed.author and embed.author.name:
                    username = embed.author.name
                    user = discord.utils.get(interaction.guild.members, name=username)
                    if user:
                        user_id = user.id
            except Exception:
                pass
        
        if not user_id:
            await interaction.response.send_message("Error: Could not identify the applicant.", ephemeral=True)
            return
        
        try:
            user = await bot.fetch_user(user_id)
            await user.send("> <:Cross:1439266290601820212> Your Content Creator application was rejected.")
            await interaction.response.send_message(f"Application rejected. {user.mention} has been notified.", ephemeral=True)
            
            if interaction.message:
                await interaction.message.edit(view=None)
        except discord.Forbidden:
            await interaction.response.send_message(f"Could not DM user (ID: {user_id}). They may have DMs disabled.", ephemeral=True)
        except Exception as e:
            print(f"Error in reject button: {e}")
            await interaction.response.send_message("An error occurred.", ephemeral=True)

@tree.command(name="cc_apply", description="Create a Content Creator application panel")
@app_commands.describe(
    color="The color of the embed (blue, red, yellow, green, purple, orange, pink, black, white)",
    channel="The channel where the panel will be posted"
)
async def cc_apply(
    interaction: discord.Interaction,
    color: str,
    channel: discord.TextChannel
):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You need Manage Server permission to use this command.", ephemeral=True)
        return
    
    color_lower = color.lower()
    if color_lower not in COLOR_MAP:
        await interaction.response.send_message(
            f"Invalid color. Available colors: {', '.join(COLOR_MAP.keys())}",
            ephemeral=True
        )
        return
    
    await interaction.response.send_message(
        "What text do you want the panel to have? (You can use server emojis)\nPlease send your response in this channel.",
        ephemeral=True
    )
    
    def check(m):
        return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id
    
    try:
        msg = await bot.wait_for('message', check=check, timeout=300.0)
        panel_text = msg.content
        
        try:
            await msg.delete()
        except Exception:
            pass
        
        embed = discord.Embed(
            description=panel_text,
            color=COLOR_MAP[color_lower]
        )
        
        view = CCApplyButtonView()
        
        try:
            await channel.send(embed=embed, view=view)
            await interaction.followup.send(f"Application panel created in {channel.mention}!", ephemeral=True)
        except Exception as e:
            print(f"Error sending panel: {e}")
            await interaction.followup.send("Failed to send the panel. Check bot permissions in that channel.", ephemeral=True)
    
    except asyncio.TimeoutError:
        await interaction.followup.send("Command timed out. Please try again.", ephemeral=True)

# ---------------- Run ----------------
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("Shutdown requested by user.")
    except Exception as e:
        print("Error starting bot:", e)