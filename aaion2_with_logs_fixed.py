import os
import re
import json
import asyncio
import random
from datetime import timedelta, datetime, timezone
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
WARNINGS_PATH = "warnings.json"

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
warnings_db: Dict[str, Dict[str, List[Dict[str, Any]]]] = load_json_file(WARNINGS_PATH, {})

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
    global panels, autoroles, warnings_db
    panels = load_json_file(DB_PATH, [])
    autoroles = load_json_file(AUTOROLES_PATH, {})
    warnings_db = load_json_file(WARNINGS_PATH, {})

    # set presence
    try:
        await bot.change_presence(activity=discord.Game(name="⛄• Stumble Hour"))
    except Exception:
        pass

    # re-register persistent views (if you have them)
    try:
        bot.add_view(CCApplyButtonView())
        bot.add_view(CCApplicationReviewView())
        bot.add_view(ModApplyButtonView())
        bot.add_view(ModApplicationReviewView())
        bot.add_view(TicketButtonView())
        bot.add_view(TicketSelectView())
        bot.add_view(TicketControlView())
    except Exception:
        pass

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

# ---------------- Lock / Unlock commands (unchanged) ----------------
SUCCESS_EMOJI = "<:SCSuccess:1439236476616310844>"
GREEN_COLOR = 0x2ECC71  # pleasant green

@bot.command(name="lock")
@commands.has_guild_permissions(manage_channels=True)
async def lock(ctx):
    try:
        try:
            await ctx.message.delete()
        except Exception:
            pass

        channel = ctx.channel
        guild = ctx.guild
        everyone = guild.default_role

        current_overwrite = channel.overwrites_for(everyone)
        read_perm = current_overwrite.read_messages if current_overwrite.read_messages is not None else True

        await channel.set_permissions(everyone, send_messages=False, read_messages=read_perm)

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
    try:
        try:
            await ctx.message.delete()
        except Exception:
            pass

        channel = ctx.channel
        everyone = ctx.guild.default_role

        eo = channel.overwrites_for(everyone)
        if eo.send_messages is not None:
            eo.send_messages = None
            await channel.set_permissions(everyone, overwrite=eo)

        for target, overwrite in list(channel.overwrites.items()):
            if overwrite.send_messages is not None:
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
    entry = {"guild_id": str(interaction.guild.id), "channel_id": str(channel.id), "message_id": str(sent.id), "created_at": discord.utils.utcnow().isoformat(), "entries": []}
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
        emoji_id = getattr(payload.emoji, "id", None)
        emoji_name = getattr(payload.emoji, "name", None)
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
        emoji_id = getattr(payload.emoji, "id", None)
        emoji_name = getattr(payload.emoji, "name", None)
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

# ---------------- Content Creator Application System (unchanged) ----------------
ADMIN_CHANNEL_ID = 1439265373697605683
SUPPORT_ROLE_ID = 1439719999349461234
TICKET_CATEGORY_NAME = "Tickets"

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
        self.question1 = discord.ui.TextInput(label="What is your discord username?", style=discord.TextStyle.short, required=True, max_length=500)
        self.question2 = discord.ui.TextInput(label="On which Platform do you Post Videos?", style=discord.TextStyle.short, required=True, max_length=500)
        self.question3 = discord.ui.TextInput(label="What content do you do?", style=discord.TextStyle.paragraph, required=True, max_length=500)
        self.question4 = discord.ui.TextInput(label="What is your age?", style=discord.TextStyle.short, required=True, max_length=500)
        self.question5 = discord.ui.TextInput(label="Why do you want to be a CC for Stumble Hour?", style=discord.TextStyle.paragraph, required=True, max_length=500)
        self.add_item(self.question1)
        self.add_item(self.question2)
        self.add_item(self.question3)
        self.add_item(self.question4)
        self.add_item(self.question5)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
            if not admin_channel:
                await interaction.response.send_message("Error: Admin channel not found.", ephemeral=True)
                return
            
            embed = discord.Embed(title="New Content Creator Application", color=0x9B59B6, timestamp=discord.utils.utcnow())
            embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text=f"Applicant ID: {interaction.user.id}")
            embed.add_field(name="Q1: What is your discord username?", value=f"A: {self.question1.value}", inline=False)
            embed.add_field(name="Q2: On which Platform do you Post Videos?", value=f"A: {self.question2.value}", inline=False)
            embed.add_field(name="Q3: What content do you do?", value=f"A: {self.question3.value}", inline=False)
            embed.add_field(name="Q4: What is your age?", value=f"A: {self.question4.value}", inline=False)
            embed.add_field(name="Q5: Why do you want to be a CC for Stumble Hour?", value=f"A: {self.question5.value}", inline=False)
            
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
    
    @discord.ui.button(label=" Accept", style=discord.ButtonStyle.success, emoji="<:SCSuccess:1439236476616310844>", custom_id="cc_review:accept")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = self.user_id
        if not user_id and interaction.message and interaction.message.embeds:
            try:
                embed = interaction.message.embeds[0]
                if embed.footer and embed.footer.text and "Applicant ID:" in embed.footer.text:
                    user_id = int(embed.footer.text.replace("Applicant ID:", "").strip())
            except Exception as e:
                print(f"Error extracting user_id from footer: {e}")
        
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
    
    @discord.ui.button(label=" Reject", style=discord.ButtonStyle.danger, emoji="<:Cross:1439266290601820212>", custom_id="cc_review:reject")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = self.user_id
        if not user_id and interaction.message and interaction.message.embeds:
            try:
                embed = interaction.message.embeds[0]
                if embed.footer and embed.footer.text and "Applicant ID:" in embed.footer.text:
                    user_id = int(embed.footer.text.replace("Applicant ID:", "").strip())
            except Exception as e:
                print(f"Error extracting user_id from footer: {e}")
        
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

@tree.command(name="cc_apply", description="Create Content Creator apply panel")
@app_commands.describe(
    color="Embed color name or hex (e.g., blue, #ff0000)",
    channel="Channel where the panel embed will be posted"
)
async def cc_apply(interaction: discord.Interaction, color: str, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You need Manage Server permission to use this command.", ephemeral=True)
        return
    
    admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
    if not admin_channel:
        await interaction.response.send_message(
            f"Error: Admin review channel (ID: {ADMIN_CHANNEL_ID}) not found. Please contact a server administrator.",
            ephemeral=True
        )
        return
    
    color_lower = color.lower()
    if color_lower not in COLOR_MAP:
        await interaction.response.send_message(f"Invalid color. Available colors: {', '.join(COLOR_MAP.keys())}", ephemeral=True)
        return
    
    await interaction.response.send_message("What text do you want the panel to have? (You can use server emojis)\nPlease send your response in this channel.", ephemeral=True)
    
    def check(m):
        return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id
    
    try:
        msg = await bot.wait_for('message', check=check, timeout=300.0)
        panel_text = msg.content
        try:
            await msg.delete()
        except Exception:
            pass
        embed = discord.Embed(description=panel_text, color=COLOR_MAP[color_lower])
        view = CCApplyButtonView()
        try:
            await channel.send(embed=embed, view=view)
            await interaction.followup.send(f"Application panel created in {channel.mention}!", ephemeral=True)
        except Exception as e:
            print(f"Error sending panel: {e}")
            await interaction.followup.send("Failed to send the panel. Check bot permissions in that channel.", ephemeral=True)
    except asyncio.TimeoutError:
        await interaction.followup.send("Command timed out. Please try again.", ephemeral=True)

# ---------------- Moderator Application System (unchanged flow) ----------------
MOD_ADMIN_CHANNEL_ID = 1439668067411165256
STAFF_EMOJI = discord.PartialEmoji(name="Staff", id=1439679153963270185)

class ModApplicationModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Moderator Application")
        self.question1 = discord.ui.TextInput(label="What is your discord username?", style=discord.TextStyle.short, required=True, max_length=500)
        self.question2 = discord.ui.TextInput(label="Do you have good Staff Experience?", style=discord.TextStyle.paragraph, required=True, max_length=500)
        self.question3 = discord.ui.TextInput(label="Why do you want to be a Staff here?", style=discord.TextStyle.paragraph, required=True, max_length=500)
        self.question4 = discord.ui.TextInput(label="What is your age?", style=discord.TextStyle.short, required=True, max_length=500)
        self.question5 = discord.ui.TextInput(label="Do you want to tell us something else?", style=discord.TextStyle.paragraph, required=True, max_length=500)
        self.add_item(self.question1)
        self.add_item(self.question2)
        self.add_item(self.question3)
        self.add_item(self.question4)
        self.add_item(self.question5)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            admin_channel = bot.get_channel(MOD_ADMIN_CHANNEL_ID)
            if not admin_channel:
                await interaction.response.send_message("Error: Admin channel not found.", ephemeral=True)
                return
            
            embed = discord.Embed(title="New Moderator Application", color=0x9B59B6, timestamp=discord.utils.utcnow())
            embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text=f"Applicant ID: {interaction.user.id}")
            embed.add_field(name="Q1: What is your discord username?", value=f"A: {self.question1.value}", inline=False)
            embed.add_field(name="Q2: Do you have good Staff Experience?", value=f"A: {self.question2.value}", inline=False)
            embed.add_field(name="Q3: Why do you want to be a Staff here?", value=f"A: {self.question3.value}", inline=False)
            embed.add_field(name="Q4: What is your age?", value=f"A: {self.question4.value}", inline=False)
            embed.add_field(name="Q5: Do you want to tell us something else?", value=f"A: {self.question5.value}", inline=False)
            
            view = ModApplicationReviewView(user_id=interaction.user.id)
            await admin_channel.send(embed=embed, view=view)
            await interaction.response.send_message("Your application has been submitted successfully!", ephemeral=True)
        except Exception as e:
            print(f"Error submitting application: {e}")
            await interaction.response.send_message("An error occurred while submitting your application.", ephemeral=True)

class ModApplyButtonView(discord.ui.View):
    def __init__(self, button_label: str = "Apply"):
        super().__init__(timeout=None)
        apply_btn = discord.ui.Button(
            label=button_label,
            style=discord.ButtonStyle.primary,
            custom_id="mod_apply:apply_button",
            emoji=STAFF_EMOJI
        )
        apply_btn.callback = self.apply_button_callback
        self.add_item(apply_btn)
    
    async def apply_button_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ModApplicationModal())

class ModApplicationReviewView(discord.ui.View):
    def __init__(self, user_id: int = None):
        super().__init__(timeout=None)
        self.user_id = user_id
    
    @discord.ui.button(label=" Accept", style=discord.ButtonStyle.success, emoji="<:SCSuccess:1439236476616310844>", custom_id="mod_review:accept")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = self.user_id
        if not user_id and interaction.message and interaction.message.embeds:
            try:
                embed = interaction.message.embeds[0]
                if embed.footer and embed.footer.text and "Applicant ID:" in embed.footer.text:
                    user_id = int(embed.footer.text.replace("Applicant ID:", "").strip())
            except Exception as e:
                print(f"Error extracting user_id from footer: {e}")
        if not user_id:
            await interaction.response.send_message("Error: Could not identify the applicant.", ephemeral=True)
            return
        try:
            user = await bot.fetch_user(user_id)
            await user.send("> <:SCSuccess:1439236476616310844> Your moderator application was accepted.")
            await interaction.response.send_message(f"Application accepted. {user.mention} has been notified.", ephemeral=True)
            if interaction.message:
                await interaction.message.edit(view=None)
        except discord.Forbidden:
            await interaction.response.send_message(f"Could not DM user (ID: {user_id}). They may have DMs disabled.", ephemeral=True)
        except Exception as e:
            print(f"Error in accept button: {e}")
            await interaction.response.send_message("An error occurred.", ephemeral=True)
    
    @discord.ui.button(label=" Reject", style=discord.ButtonStyle.danger, emoji="<:Cross:1439266290601820212>", custom_id="mod_review:reject")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = self.user_id
        if not user_id and interaction.message and interaction.message.embeds:
            try:
                embed = interaction.message.embeds[0]
                if embed.footer and embed.footer.text and "Applicant ID:" in embed.footer.text:
                    user_id = int(embed.footer.text.replace("Applicant ID:", "").strip())
            except Exception as e:
                print(f"Error extracting user_id from footer: {e}")
        if not user_id:
            await interaction.response.send_message("Error: Could not identify the applicant.", ephemeral=True)
            return
        try:
            user = await bot.fetch_user(user_id)
            await user.send("> <:Cross:1439266290601820212> Your moderator application was rejected.")
            await interaction.response.send_message(f"Application rejected. {user.mention} has been notified.", ephemeral=True)
            if interaction.message:
                await interaction.message.edit(view=None)
        except discord.Forbidden:
            await interaction.response.send_message(f"Could not DM user (ID: {user_id}). They may have DMs disabled.", ephemeral=True)
        except Exception as e:
            print(f"Error in reject button: {e}")
            await interaction.response.send_message("An error occurred.", ephemeral=True)

# ---------------- Add /mod_apply command ----------------
@tree.command(name="mod_apply", description="Create a Moderator application panel")
@app_commands.describe(
    color="The color of the embed (blue, red, yellow, green, purple, orange, pink, black, white)",
    channel="The channel where the panel will be posted"
)
async def mod_apply(interaction: discord.Interaction, color: str, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You need Manage Server permission to use this command.", ephemeral=True)
        return

    color_lower = color.lower()
    if color_lower not in COLOR_MAP:
        await interaction.response.send_message(f"Invalid color. Available colors: {', '.join(COLOR_MAP.keys())}", ephemeral=True)
        return

    await interaction.response.send_message("What text do you want the panel to have? (You can use server emojis)\nPlease send your response in this channel.", ephemeral=True)

    def check(m: discord.Message):
        return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

    try:
        msg = await bot.wait_for('message', check=check, timeout=300.0)
        panel_text = msg.content
        try:
            await msg.delete()
        except Exception:
            pass

        embed = discord.Embed(description=panel_text or "\u200b", color=COLOR_MAP[color_lower])
        view = ModApplyButtonView(button_label="Apply")
        try:
            await channel.send(embed=embed, view=view)
            await interaction.followup.send(f"Moderator application panel created in {channel.mention}!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to send messages in the target channel.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Failed to create panel: {e}", ephemeral=True)
    except asyncio.TimeoutError:
        await interaction.followup.send("Timed out waiting for the panel text.", ephemeral=True)

# ---------------- Ticket System ----------------
class TicketSelectMenu(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="General Support",
                description="General Stumble Hour Support",
                value="general_support",
                emoji="🎫"
            ),
            discord.SelectOption(
                label="Bug",
                description="I need help with a bug",
                value="bug",
                emoji="🐛"
            )
        ]
        super().__init__(
            placeholder="Select a ticket type...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_select_menu"
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user
        
        ticket_type = self.values[0]
        
        if ticket_type == "general_support":
            channel_name = f"general-support-{user.name}"
        elif ticket_type == "bug":
            channel_name = f"bug-{user.name}"
        else:
            channel_name = f"ticket-{user.name}"
        
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(TICKET_CATEGORY_NAME)
        
        support_role = guild.get_role(SUPPORT_ROLE_ID)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            for role in guild.roles:
                if role.position > support_role.position:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        ticket_channel = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites
        )
        
        embed = discord.Embed(
            description=f"Hello, describe us your problem and one of our staffs will come and help you soon! <:Hug:1439240590289276985>",
            color=discord.Color.purple()
        )
        
        view = TicketControlView()
        await ticket_channel.send(content=user.mention, embed=embed, view=view)
        
        await interaction.response.send_message(
            f"Ticket created! Check {ticket_channel.mention}",
            ephemeral=True
        )


class TicketSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelectMenu())


class OpenTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Open ticket",
            style=discord.ButtonStyle.primary,
            emoji="<:guildmanager_ticket:1440052221545938984>",
            custom_id="open_ticket_button"
        )

    async def callback(self, interaction: discord.Interaction):
        view = TicketSelectView()
        await interaction.response.send_message(
            "Please select the type of support you need:",
            view=view,
            ephemeral=True
        )


class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(OpenTicketButton())


class CloseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Close",
            style=discord.ButtonStyle.primary,
            emoji="🔒",
            custom_id="close_ticket_button"
        )

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            description=f"Ticket closed by {interaction.user.mention}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user.name}")


class ClaimButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Claim",
            style=discord.ButtonStyle.secondary,
            emoji="<:SCSuccess:1439236476616310844>",
            custom_id="claim_ticket_button"
        )

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            description=f"{interaction.user.mention} has claimed the ticket. He will help you with your problem as soon as possible!",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        self.disabled = True
        await interaction.message.edit(view=self.view)


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CloseButton())
        self.add_item(ClaimButton())


@bot.command(name="ticket")
@commands.has_permissions(administrator=True)
async def ticket_command(ctx):
    embed = discord.Embed(
        description="Welcome to our ticket Support! Please only open a ticket if you need Support about ingame problems or Server Problems. <:starIcon:1440052314051182775>",
        color=discord.Color.blue()
    )
    
    view = TicketButtonView()
    await ctx.send(embed=embed, view=view)
    
    try:
        await ctx.message.delete()
    except:
        pass

# ---------------- Replaced Game Command (your requested implementation with custom separator)
# Modified: after running, shows an ephemeral confirmation to the invoker and posts the panel to the channel.
@tree.command(name="game", description="Change game download panel")
@app_commands.describe(
    sg_build_vers="Stumble Guys build version",
    stumble_hour_build_vers="Stumble Hour build version",
    phone_link="Phone download link",
    pc_link="PC game folder link",
    dll_link="Loader DLL link"
)
async def game(
    interaction: discord.Interaction,
    sg_build_vers: str,
    stumble_hour_build_vers: str,
    phone_link: str,
    pc_link: str,
    dll_link: str
):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You need Manage Server permission to use this command.", ephemeral=True)
        return

    unix_time = int(datetime.now(tz=timezone.utc).timestamp())

    embed = discord.Embed(title="Stumble Hour Downloads", color=discord.Color.yellow())

    # server icon top-right
    if interaction.guild and interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)

    # Field 1: versions
    embed.add_field(
        name="",
        value=(
            f"⏱️ Last Updated: <t:{unix_time}:R>\n"
            f"🔹 Stumble Guys build version: {sg_build_vers}\n"
            f"🔸 Stumble Hour version: {stumble_hour_build_vers}"
        ),
        inline=False
    )

    # visible separator using the requested character
    separator_line = "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
    embed.add_field(name="\u200b", value=separator_line, inline=False)

    # Phone download row: left = label, right = clickable link (markdown) shown inside embed
    embed.add_field(name="📱 Phone download", value="<:BF:1442503402968842371> Android", inline=True)
    embed.add_field(name="\u200b", value=f"[Download phone]({phone_link})", inline=True)

    # separator
    embed.add_field(name="\u200b", value=separator_line, inline=False)

    # PC download row
    embed.add_field(name="💻 Pc download", value="<:BF:1442503402968842371> Game folder", inline=True)
    embed.add_field(name="\u200b", value=f"[PC download]({pc_link})", inline=True)

    # separator
    embed.add_field(name="\u200b", value=separator_line, inline=False)

    # Loader DLL row
    embed.add_field(name="<:sg_check:1442516721658495056> Loader DLL", value="<:BF:1442503402968842371> Pc loader", inline=True)
    embed.add_field(name="\u200b", value=f"[Loader DLL]({dll_link})", inline=True)

    # Send ephemeral confirmation to invoker and post the panel publicly in the channel
    try:
        await interaction.response.send_message("Panel sent successfully!", ephemeral=True)
        # Post panel to channel as a followup (visible to everyone)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        # If followup fails, attempt to at least respond with an error
        try:
            await interaction.followup.send(f"Failed to send panel: {e}", ephemeral=True)
        except Exception:
            pass

# ---------------- Custom Embed Command ----------------
def parse_color(color_input: str) -> int:
    color_lower = color_input.lower().strip()
    if color_lower in COLOR_MAP:
        return COLOR_MAP[color_lower]
    if color_input.startswith('#'):
        try:
            return int(color_input[1:], 16)
        except ValueError:
            return None
    return None

@tree.command(name="embed", description="Create a custom embed in a specific channel")
@app_commands.describe(
    color="Color of the embed (blue, red, yellow, etc. or hex like #FF0000)",
    channel="Channel where the embed will be sent",
    picture="Optional: Image URL for the embed"
)
async def embed_command(
    interaction: discord.Interaction,
    color: str,
    channel: discord.TextChannel,
    picture: Optional[str] = None
):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You need Manage Server permission to use this command.", ephemeral=True)
        return
    
    parsed_color = parse_color(color)
    if parsed_color is None:
        await interaction.response.send_message(f"Invalid color. Use color names (blue, red, yellow, etc.) or hex codes (#FF0000)", ephemeral=True)
        return
    
    if picture and not is_valid_url(picture):
        await interaction.response.send_message("Invalid picture URL. Please provide a valid http:// or https:// URL.", ephemeral=True)
        return
    
    await interaction.response.send_message("What message you want to be in embed? (The first message you send here will be used)", ephemeral=True)
    
    def check(m):
        return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id
    
    try:
        msg = await bot.wait_for('message', check=check, timeout=300.0)
        embed_content = msg.content
        try:
            await msg.delete()
        except Exception:
            pass
        
        embed = discord.Embed(description=embed_content, color=parsed_color)
        
        if picture:
            embed.set_image(url=picture)
        
        try:
            await channel.send(embed=embed)
            await interaction.followup.send(f"Embed sent to {channel.mention}!", ephemeral=True)
        except Exception as e:
            print(f"Error sending embed: {e}")
            await interaction.followup.send("Failed to send the embed. Check bot permissions in that channel.", ephemeral=True)
    except asyncio.TimeoutError:
        await interaction.followup.send("Command timed out. Please try again.", ephemeral=True)

# ---------------- Warnings persistence, listing and deletion via modal/button ----------------

def ensure_guild_user_warnings(guild_id: str, user_id: str):
    if guild_id not in warnings_db:
        warnings_db[guild_id] = {}
    if user_id not in warnings_db[guild_id]:
        warnings_db[guild_id][user_id] = []

@bot.command(name="warn")
@commands.has_guild_permissions(moderate_members=True)
async def warn(ctx, member: discord.Member = None, *, reason: str = "No reason provided"):
    if member is None:
        await ctx.send("Please mention a member to warn. Usage: `!warn @user [reason]`")
        return
    if member.id == ctx.author.id:
        await ctx.send("You cannot warn yourself.")
        return
    if member.bot:
        await ctx.send("You cannot warn bots.")
        return
    try:
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)
        ensure_guild_user_warnings(guild_id, user_id)
        entry = {
            "moderator_id": ctx.author.id,
            "moderator": str(ctx.author),
            "reason": reason,
            "timestamp": discord.utils.utcnow().isoformat()
        }
        warnings_db[guild_id][user_id].append(entry)
        save_json_file(WARNINGS_PATH, warnings_db)

        embed = discord.Embed(title="Member Warned", color=0xFFA500, timestamp=discord.utils.utcnow())
        embed.add_field(name="Member", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="Warned by", value=f"{ctx.author.mention}", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

@warn.error
async def warn_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need the Moderate Members permission to use this command.", delete_after=8)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("Member not found.", delete_after=8)
    else:
        await ctx.send(f"Error: {error}", delete_after=8)

# ---------------- Command shortcuts and moderation commands continue as before ----------------
@bot.command(name="delwarn")
@commands.has_guild_permissions(moderate_members=True)
async def delwarn(ctx, member: discord.Member = None, warn_number: int = None):
    if member is None or warn_number is None:
        await ctx.send("Usage: `!delwarn @user <warn_number>`")
        return
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)
    guild_warns = warnings_db.get(guild_id, {})
    user_warns = guild_warns.get(user_id, [])
    if not user_warns:
        await ctx.send("This user has no warnings.")
        return
    if warn_number < 1 or warn_number > len(user_warns):
        await ctx.send(f"Invalid warn number. Provide a number between 1 and {len(user_warns)}")
        return
    removed = user_warns.pop(warn_number - 1)
    if len(user_warns) == 0:
        guild_warns.pop(user_id, None)
    warnings_db[guild_id] = guild_warns
    save_json_file(WARNINGS_PATH, warnings_db)
    await ctx.send(f"Deleted warning #{warn_number} for {member.mention}.")

@bot.command(name="ban")
@commands.has_guild_permissions(ban_members=True)
async def ban(ctx, member: discord.Member = None, *, reason: str = "No reason provided"):
    if member is None:
        await ctx.send("Please mention a member to ban. Usage: `!ban @user [reason]`")
        return
    if member.id == ctx.author.id:
        await ctx.send("You cannot ban yourself.")
        return
    try:
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send("You cannot ban someone with a role equal to or higher than yours.")
            return
    except Exception:
        pass
    try:
        # Do NOT attempt to DM the member before banning (avoids 50007)
        await member.ban(reason=f"{ctx.author}: {reason}")
        embed = discord.Embed(title="Member Banned", color=0xE74C3C, timestamp=discord.utils.utcnow())
        embed.add_field(name="Member", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="Banned by", value=f"{ctx.author.mention}", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to ban this member.")
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

@bot.command(name="mute")
@commands.has_guild_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member = None, duration: str = "60s", *, reason: str = "No reason provided"):
    if member is None:
        await ctx.send("Please mention a member to mute. Usage: `!mute @user [duration] [reason]`")
        return
    if member.id == ctx.author.id:
        await ctx.send("You cannot mute yourself.")
        return
    if member.bot:
        await ctx.send("You cannot mute bots.")
        return
    try:
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send("You cannot mute someone with a role equal to or higher than yours.")
            return
    except Exception:
        pass
    if not duration or len(duration) < 2:
        await ctx.send("Invalid duration format. Use: 60s, 10m, 2h, or 1d")
        return
    num_part = duration[:-1]
    unit = duration[-1].lower()
    try:
        amount = int(num_part)
    except ValueError:
        await ctx.send("Invalid duration number. Use: 60s, 10m, 2h, or 1d")
        return
    if amount <= 0:
        await ctx.send("Duration must be greater than 0.")
        return
    if unit == 's':
        seconds = amount
    elif unit == 'm':
        seconds = amount * 60
    elif unit == 'h':
        seconds = amount * 3600
    elif unit == 'd':
        seconds = amount * 86400
    else:
        await ctx.send("Invalid duration unit. Use s, m, h, or d.")
        return
    if seconds > 2419200:  # 28 days
        await ctx.send("Maximum timeout duration is 28 days.")
        return
    try:
        timeout_until = discord.utils.utcnow() + timedelta(seconds=seconds)
        # discord.Member.timeout expects an aware datetime (discord.utils.utcnow() returns aware)
        # Use positional call first for compatibility, fallback to keyword if necessary
        try:
            await member.timeout(timeout_until, reason=f"{ctx.author}: {reason}")
        except TypeError:
            await member.timeout(until=timeout_until, reason=f"{ctx.author}: {reason}")
        embed = discord.Embed(title="Member Muted", color=0xFFA500, timestamp=discord.utils.utcnow())
        embed.add_field(name="Member", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="Muted by", value=f"{ctx.author.mention}", inline=False)
        embed.add_field(name="Duration", value=duration, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to timeout this member.")
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

@bot.command(name="unmute")
@commands.has_guild_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send("Please mention a member to unmute. Usage: `!unmute @user`")
        return
    try:
        try:
            await member.timeout(None, reason=f"Unmuted by {ctx.author}")
        except TypeError:
            await member.timeout(until=None, reason=f"Unmuted by {ctx.author}")
        embed = discord.Embed(title="Member Unmuted", color=0x2ECC71, timestamp=discord.utils.utcnow())
        embed.add_field(name="Member", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="Unmuted by", value=f"{ctx.author.mention}", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to remove timeout from this member.")
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

# ---------------- Run ----------------
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("Shutdown requested by user.")
    except Exception as e:
        print("Error starting bot:", e)



# ---------------------------
# Logging Cog (integrated module)
# ---------------------------
from discord.ext import commands
import asyncio

LOGS_JSON_PATH = "logs.json"

def ensure_logs_json():
    if not os.path.exists(LOGS_JSON_PATH):
        try:
            with open(LOGS_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

def load_logs_json() -> dict:
    try:
        with open(LOGS_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
    except Exception:
        return {}

def save_logs_json(data: dict):
    try:
        with open(LOGS_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("Failed to save logs.json:", e)

class LoggingCog(commands.Cog):
    """Cog that provides server-wide logging (message delete/edit, nickname, role add/remove, mute/unmute, ban/unban)."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        ensure_logs_json()

    # Helper to get the configured log channel for a guild
    def _get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        if guild is None:
            return None
        data = load_logs_json()
        gid = str(guild.id)
        if gid not in data:
            return None
        cid = data[gid].get("log_channel")
        if cid is None:
            return None
        try:
            return guild.get_channel(int(cid)) or self.bot.get_channel(int(cid))
        except Exception:
            return None

    # Command to set logs channel (admin only)
    @commands.command(name="logs")
    @commands.has_permissions(administrator=True)
    async def set_logs(self, ctx: commands.Context, channel: discord.TextChannel):
        \"\"\"Set the logs channel for this server. Usage: !logs #channel\"\"\"
        data = load_logs_json()
        data[str(ctx.guild.id)] = {"log_channel": str(channel.id)}
        save_logs_json(data)
        embed = discord.Embed(title=\"Logs Channel Set\", description=f\"All logs will be sent to {channel.mention}\", color=0x2b2d31)
        await ctx.send(embed=embed)

    async def _get_audit_executor(self, guild: discord.Guild, action: discord.AuditLogAction, target_id: Optional[int] = None, limit: int = 8, delay: float = 1.0):
        \"\"\"Robust helper to fetch the executor from audit logs. Returns a discord.User or None.\"\"\"
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            async for entry in guild.audit_logs(limit=limit, action=action):
                try:
                    tid = getattr(entry.target, \"id\", None)
                except Exception:
                    tid = None
                if target_id is None or tid == target_id:
                    return entry.user
        except discord.Forbidden:
            # missing VIEW_AUDIT_LOG
            return None
        except Exception:
            return None
        return None

    # MESSAGE DELETE
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        try:
            if message.author is None or message.author.bot:
                return
            guild = message.guild
            if guild is None:
                return
            ch = self._get_log_channel(guild)
            if ch is None:
                return
            embed = discord.Embed(title=\"Message Deleted\", color=0xFF4444)
            embed.add_field(name=\"User:\", value=message.author.mention)
            embed.add_field(name=\"Channel:\", value=message.channel.mention)
            embed.add_field(name=\"Content:\", value=message.content or \"None\", inline=False)
            embed.set_footer(text=f\"User ID: {message.author.id} • Message ID: {message.id}\")
            await ch.send(embed=embed)
        except Exception:
            logger.exception(\"LoggingCog.on_message_delete error\")

    # MESSAGE EDIT
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        try:
            if before.author is None or before.author.bot:
                return
            if before.guild is None:
                return
            if before.content == after.content:
                return
            guild = before.guild
            ch = self._get_log_channel(guild)
            if ch is None:
                return
            embed = discord.Embed(title=\"Message Edited\", color=0xFFCC00)
            embed.add_field(name=\"User:\", value=before.author.mention)
            embed.add_field(name=\"Channel:\", value=before.channel.mention)
            embed.add_field(name=\"Before:\", value=before.content or \"None\", inline=False)
            embed.add_field(name=\"After:\", value=after.content or \"None\", inline=False)
            embed.set_footer(text=f\"User ID: {before.author.id} • Message ID: {before.id}\")
            await ch.send(embed=embed)
        except Exception:
            logger.exception(\"LoggingCog.on_message_edit error\")

    # BAN
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        try:
            ch = self._get_log_channel(guild)
            if ch is None:
                return
            executor = await self._get_audit_executor(guild, discord.AuditLogAction.ban, target_id=getattr(user, \"id\", None), delay=1.0)
            exec_text = safe_mention(executor) if executor else \"Unknown\"
            user_text = getattr(user, \"mention\", None) or f\"{user} (ID: {getattr(user, 'id', 'Unknown')})\"
            embed = discord.Embed(title=\"User Banned\", color=0x990000)
            embed.add_field(name=\"User:\", value=user_text)
            embed.add_field(name=\"Executor:\", value=exec_text)
            embed.add_field(name=\"Ban Duration:\", value=\"Permanent\")
            embed.set_footer(text=f\"User ID: {getattr(user, 'id', 'Unknown')}\")
            await ch.send(embed=embed)
        except Exception:
            logger.exception(\"LoggingCog.on_member_ban error\")

    # UNBAN
    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        try:
            ch = self._get_log_channel(guild)
            if ch is None:
                return
            executor = await self._get_audit_executor(guild, discord.AuditLogAction.unban, target_id=getattr(user, \"id\", None), delay=1.0)
            exec_text = safe_mention(executor) if executor else \"Unknown\"
            user_text = getattr(user, \"mention\", None) or f\"{user} (ID: {getattr(user, 'id', 'Unknown')})\"
            embed = discord.Embed(title=\"User Unbanned\", color=0x009933)
            embed.add_field(name=\"User:\", value=user_text)
            embed.add_field(name=\"Executor:\", value=exec_text)
            embed.set_footer(text=f\"User ID: {getattr(user, 'id', 'Unknown')}\")
            await ch.send(embed=embed)
        except Exception:
            logger.exception(\"LoggingCog.on_member_unban error\")

    # MEMBER UPDATE (nickname, roles, mute/unmute)
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        try:
            guild = before.guild
            if guild is None:
                return
            ch = self._get_log_channel(guild)
            if ch is None:
                return

            async def fetch_exec(action, target_id=None):
                e = await self._get_audit_executor(guild, action, target_id=target_id, delay=1.0)
                return (safe_mention(e) if e else \"Unknown\", e)

            # Nickname changed
            if before.nick != after.nick:
                exec_text, _ = await fetch_exec(discord.AuditLogAction.member_update, target_id=after.id)
                embed = discord.Embed(title=\"Nickname Changed\", color=0x7289DA)
                embed.add_field(name=\"User:\", value=after.mention)
                embed.add_field(name=\"Executor:\", value=exec_text)
                embed.add_field(name=\"Before:\", value=(before.nick or before.name), inline=False)
                embed.add_field(name=\"After:\", value=(after.nick or after.name), inline=False)
                embed.set_footer(text=f\"User ID: {after.id}\")
                await ch.send(embed=embed)

            # Roles added
            added_roles = [r for r in after.roles if r not in before.roles]
            if added_roles:
                role = added_roles[0]
                exec_text, _ = await fetch_exec(discord.AuditLogAction.member_role_update, target_id=after.id)
                embed = discord.Embed(title=\"Role Add\", color=0x00AAFF)
                embed.add_field(name=\"User:\", value=after.mention)
                embed.add_field(name=\"Executor:\", value=exec_text)
                embed.add_field(name=\"Role Added:\", value=role.mention)
                embed.set_footer(text=f\"Role ID: {role.id} • User ID: {after.id}\")
                await ch.send(embed=embed)

            # Roles removed
            removed_roles = [r for r in before.roles if r not in after.roles]
            if removed_roles:
                role = removed_roles[0]
                exec_text, _ = await fetch_exec(discord.AuditLogAction.member_role_update, target_id=after.id)
                embed = discord.Embed(title=\"Role Removed\", color=0xFF3333)
                embed.add_field(name=\"User:\", value=after.mention)
                embed.add_field(name=\"Executor:\", value=exec_text)
                embed.add_field(name=\"Role Removed:\", value=role.mention)
                embed.set_footer(text=f\"Role ID: {role.id} • User ID: {after.id}\")
                await ch.send(embed=embed)

            # Mute/unmute by role name
            mute_role = discord.utils.get(guild.roles, name=MUTE_ROLE_NAME)
            if mute_role:
                if mute_role not in before.roles and mute_role in after.roles:
                    exec_text, _ = await fetch_exec(discord.AuditLogAction.member_role_update, target_id=after.id)
                    embed = discord.Embed(title=\"User Muted\", color=0xFF6600)
                    embed.add_field(name=\"User:\", value=after.mention)
                    embed.add_field(name=\"Executor:\", value=exec_text)
                    embed.add_field(name=\"Mute Duration:\", value=\"Unknown\")
                    embed.set_footer(text=f\"Role ID: {mute_role.id} • User ID: {after.id}\")
                    await ch.send(embed=embed)
                if mute_role in before.roles and mute_role not in after.roles:
                    exec_text, _ = await fetch_exec(discord.AuditLogAction.member_role_update, target_id=after.id)
                    embed = discord.Embed(title=\"User Unmuted\", color=0x33CC33)
                    embed.add_field(name=\"User:\", value=after.mention)
                    embed.add_field(name=\"Executor:\", value=exec_text)
                    embed.set_footer(text=f\"Role ID: {mute_role.id} • User ID: {after.id}\")
                    await ch.send(embed=embed)
        except Exception:
            logger.exception(\"LoggingCog.on_member_update error\")

# Register the cog
try:
    bot.add_cog(LoggingCog(bot))
    print(\"LoggingCog loaded successfully.\")
except Exception as e:
    print(\"Failed to load LoggingCog:\", e)

