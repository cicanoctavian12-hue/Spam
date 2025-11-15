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
APPLICATIONS_PATH = "applications.json"

if not TOKEN:
    print("ERROR: TOKEN environment variable not set. Exiting.")
    raise SystemExit(1)

# Intents
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True
intents.reactions = True

# Bot
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

# Load persisted files (if missing, returns defaults)
panels: List[Dict[str, Any]] = load_json_file(DB_PATH, [])
autoroles: Dict[str, str] = load_json_file(AUTOROLES_PATH, {})
applications: Dict[str, Any] = load_json_file(APPLICATIONS_PATH, {})

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

COLOR_MAP = {
    "red": 0xFF0000, "blue": 0x0000FF, "green": 0x00FF00, "yellow": 0xFFFF00,
    "orange": 0xFFA500, "purple": 0x800080, "pink": 0xFFC0CB, "black": 0x000000,
    "white": 0xFFFFFF, "grey": 0x808080, "gray": 0x808080, "teal": 0x008080,
    "gold": 0xFFD700, "default": 0x00AE86
}

def parse_color(value: str) -> int:
    if not value:
        return COLOR_MAP["default"]
    v = value.strip().lower()
    if v in COLOR_MAP:
        return COLOR_MAP[v]
    if v.startswith("#"):
        v = v[1:]
    if re.fullmatch(r"[0-9a-f]{6}", v):
        return int(v, 16)
    return COLOR_MAP["default"]

def is_valid_url(u: str) -> bool:
    return isinstance(u, str) and (u.startswith("http://") or u.startswith("https://"))

def is_valid_channel(ch: discord.TextChannel) -> bool:
    return isinstance(ch, discord.TextChannel)

# ---------------- Persistent IDs & emojis ----------------
APPLY_BUTTON_CUSTOM_ID = "cc_apply_btn_v1"
ACCEPT_BUTTON_CUSTOM_ID = "cc_accept_btn_v1"
REJECT_BUTTON_CUSTOM_ID = "cc_reject_btn_v1"

# PartialEmoji placeholders (bot must have access to custom emojis for them to render)
CREATOR_ICON = discord.PartialEmoji(name="CreatorIcon", id=1439238460270444594)
SCSUCCESS = discord.PartialEmoji(name="SCSuccess", id=1439236476616310844)
CROSS = discord.PartialEmoji(name="Cross", id=1439266290601820212)

STAFF_CHANNEL_ID = 1439265373697605683  # staff channel for applications

# ---------------- Application Modal ----------------
class ApplicationModal(discord.ui.Modal, title="Content Creator Application"):
    def __init__(self, panel_message_id: Optional[int] = None):
        super().__init__()
        self.panel_message_id = panel_message_id

    username = discord.ui.TextInput(label="1. What is your discord username?", style=discord.TextStyle.short, max_length=500, required=True)
    platform_play = discord.ui.TextInput(label="2. On which Platform do you play?", style=discord.TextStyle.short, max_length=500, required=True)
    platform_post = discord.ui.TextInput(label="3. On which Platform do you Post Videos?", style=discord.TextStyle.short, max_length=500, required=True)
    content_type = discord.ui.TextInput(label="4. What content do you do?", style=discord.TextStyle.paragraph, max_length=500, required=True)
    age = discord.ui.TextInput(label="5. What is your age?", style=discord.TextStyle.short, max_length=500, required=True)
    why_apply = discord.ui.TextInput(label="6. Why do you want to be a Content Creator for Stumble Hour?", style=discord.TextStyle.paragraph, max_length=500, required=True)
    anything_else = discord.ui.TextInput(label="7. Anything else, what you want to tell us?", style=discord.TextStyle.paragraph, max_length=500, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        applicant = interaction.user
        answers = {
            "1": self.username.value,
            "2": self.platform_play.value,
            "3": self.platform_post.value,
            "4": self.content_type.value,
            "5": self.age.value,
            "6": self.why_apply.value,
            "7": self.anything_else.value
        }

        embed = discord.Embed(title="Content Creator Application", color=0x7B3FBF)  # purple
        q_map = {
            1: "What is your discord username?",
            2: "On which Platform do you play?",
            3: "On which Platform do you Post Videos?",
            4: "What content do you do?",
            5: "What is your age?",
            6: "Why do you want to be an Content Creator for Stumble Hour?",
            7: "Anything else, what you want to tell us?"
        }
        parts = []
        for i in range(1, 8):
            parts.append(f"Q:{i}. {q_map[i]}\nA: {answers[str(i)]}")
        embed.description = "\n\n".join(parts)
        embed.set_author(name=str(applicant), icon_url=applicant.display_avatar.url if hasattr(applicant, "display_avatar") else None)
        embed.timestamp = datetime.utcnow()

        # send to staff channel
        target_channel = interaction.client.get_channel(STAFF_CHANNEL_ID)
        if target_channel is None:
            try:
                target_channel = await interaction.client.fetch_channel(STAFF_CHANNEL_ID)
            except Exception:
                await interaction.response.send_message("Failed to post application to staff channel. Contact an admin.", ephemeral=True)
                return

        view = ApplicationDecisionView()
        sent = await target_channel.send(embed=embed, view=view)

        # persist mapping
        applications[str(sent.id)] = {
            "applicant_id": applicant.id,
            "answers": answers,
            "panel_message_id": self.panel_message_id,
            "submitted_at": datetime.utcnow().isoformat()
        }
        save_json_file(APPLICATIONS_PATH, applications)

        await interaction.response.send_message("✅ Application submitted! Staff will review it.", ephemeral=True)

# ---------------- Decision View ----------------
class ApplicationDecisionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id=ACCEPT_BUTTON_CUSTOM_ID, emoji=SCSUCCESS)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        # permission check
        if not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.manage_messages or interaction.user.guild_permissions.manage_roles):
            await interaction.response.send_message("You don't have permission to accept applications.", ephemeral=True)
            return

        app_msg_id = str(interaction.message.id)
        entry = applications.get(app_msg_id)
        if not entry:
            await interaction.response.send_message("Application data not found.", ephemeral=True)
            return

        applicant_id = entry.get("applicant_id")
        try:
            user = await bot.fetch_user(applicant_id)
            await user.send(f"{SCSUCCESS} Your Content Creator application was accepted.")
        except Exception:
            pass

        # disable buttons and update footer
        for item in self.children:
            item.disabled = True
        embed = interaction.message.embeds[0] if interaction.message.embeds else None
        if embed:
            embed.set_footer(text=f"Accepted by {interaction.user}", icon_url=getattr(interaction.user, "display_avatar", None).url if getattr(interaction.user, "display_avatar", None) else None)
        await interaction.message.edit(embed=embed, view=self)

        applications.pop(app_msg_id, None)
        save_json_file(APPLICATIONS_PATH, applications)

        await interaction.response.send_message("Application accepted and applicant notified.", ephemeral=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id=REJECT_BUTTON_CUSTOM_ID, emoji=CROSS)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.manage_messages or interaction.user.guild_permissions.manage_roles):
            await interaction.response.send_message("You don't have permission to reject applications.", ephemeral=True)
            return

        app_msg_id = str(interaction.message.id)
        entry = applications.get(app_msg_id)
        if not entry:
            await interaction.response.send_message("Application data not found.", ephemeral=True)
            return

        applicant_id = entry.get("applicant_id")
        try:
            user = await bot.fetch_user(applicant_id)
            await user.send(f"{CROSS} Your Content Creator application was rejected.")
        except Exception:
            pass

        for item in self.children:
            item.disabled = True
        embed = interaction.message.embeds[0] if interaction.message.embeds else None
        if embed:
            embed.set_footer(text=f"Rejected by {interaction.user}", icon_url=getattr(interaction.user, "display_avatar", None).url if getattr(interaction.user, "display_avatar", None) else None)
        await interaction.message.edit(embed=embed, view=self)

        applications.pop(app_msg_id, None)
        save_json_file(APPLICATIONS_PATH, applications)

        await interaction.response.send_message("Application rejected and applicant notified.", ephemeral=True)

# ---------------- Apply Button View ----------------
class ApplyButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Apply here Apply here", style=discord.ButtonStyle.primary, custom_id=APPLY_BUTTON_CUSTOM_ID, emoji=CREATOR_ICON)
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        panel_msg_id = interaction.message.id if interaction.message else None
        modal = ApplicationModal(panel_message_id=panel_msg_id)
        await interaction.response.send_modal(modal)

# Register persistent views at import time so callbacks are available immediately after the bot starts.
# This prevents "This interaction failed" for buttons created in previous runs.
try:
    bot.add_view(ApplyButtonView())
    bot.add_view(ApplicationDecisionView())
except Exception:
    pass

# ---------------- /cc_apply slash command ----------------
@tree.command(name="cc_apply", description="Create Content Creator apply panel")
@app_commands.describe(
    color="Embed color name or hex (e.g., blue, #ff0000)",
    channel="Channel where the panel embed will be posted"
)
async def cc_apply(interaction: discord.Interaction, color: str, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    if not is_valid_channel(channel):
        await interaction.response.send_message("Invalid channel provided.", ephemeral=True)
        return

    embed_color = parse_color(color)

    await interaction.response.send_message("What text you want the panel to have?", ephemeral=False)

    def check(m: discord.Message):
        return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

    try:
        msg = await bot.wait_for('message', timeout=300.0, check=check)
    except asyncio.TimeoutError:
        await interaction.followup.send("Timed out waiting for the panel text.", ephemeral=True)
        return

    panel_text = msg.content

    embed = discord.Embed(description=panel_text or "\u200b", color=embed_color)
    view = ApplyButtonView()
    try:
        await channel.send(embed=embed, view=view)
        await interaction.followup.send("Panel created.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("I don't have permission to send messages in the target channel.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Failed to create panel: {e}", ephemeral=True)

# ---------------- Autorole system ----------------
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

# ---------------- Reaction-role panel (slash) ----------------
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

# ---------------- Reaction add/remove handlers ----------------
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

# ---------------- /embed command ----------------
@tree.command(name="embed", description="Create an embed in a channel by replying with the message.")
@app_commands.describe(channel="Target channel", color="Color name or hex", picture="Optional image URL")
async def embed_command(interaction: discord.Interaction, channel: discord.TextChannel, color: str, picture: Optional[str] = None):
    if picture and not is_valid_url(picture):
        await interaction.response.send_message("Picture must be a valid URL starting with http:// or https://", ephemeral=True)
        return
    try:
        color_int = parse_color(color)
    except Exception as e:
        await interaction.response.send_message(f"Invalid color: {e}", ephemeral=True)
        return
    await interaction.response.send_message("What message you want to be in embed? (first message you send here will be used)", ephemeral=False)
    def check(m: discord.Message):
        return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id
    try:
        msg = await bot.wait_for('message', timeout=180.0, check=check)
    except asyncio.TimeoutError:
        await interaction.followup.send("Timed out waiting for your message.", ephemeral=True)
        return
    content = msg.content
    if not content:
        await interaction.followup.send("Empty message. Aborting.", ephemeral=True)
        return
    embed = discord.Embed(description=content, color=color_int)
    if picture:
        embed.set_image(url=picture)
    try:
        await channel.send(embed=embed)
        await interaction.followup.send(f"Embed sent to {channel.mention}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("I don't have permission to send embeds in the target channel.", ephemeral=True)

# ---------------- /game command (each embed its own message) ----------------
@tree.command(name="game", description="Create a downloads/info panel with optional link buttons.")
@app_commands.describe(
    channel="Channel where the embed will be posted (required)",
    phone_link="Optional phone (APK) link",
    pc_link="Optional PC (game folder) link",
    loader_link="Optional loader/DLL link"
)
async def game_command(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    phone_link: Optional[str] = None,
    pc_link: Optional[str] = None,
    loader_link: Optional[str] = None,
):
    if not interaction.user.guild_permissions.send_messages:
        await interaction.response.send_message("You don't have permission to use this.", ephemeral=True)
        return
    for name, link in (("phone", phone_link), ("pc", pc_link), ("loader", loader_link)):
        if link and not is_valid_url(link):
            await interaction.response.send_message(f"{name}_link must be a valid http(s) URL.", ephemeral=True)
            return
    prompts = []
    if phone_link:
        prompts.append(("phone", phone_link, "What text you want for the phone link embed?"))
    if pc_link:
        prompts.append(("pc", pc_link, "What text you want for the pc link embed?"))
    if loader_link:
        prompts.append(("loader", loader_link, "What text you want for the loader link embed?"))
    if not prompts:
        await interaction.response.send_message("You must provide at least one link option in the command.", ephemeral=True)
        return
    await interaction.response.send_message(prompts[0][2], ephemeral=False)
    def check(m: discord.Message):
        return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id
    collected = {}
    try:
        for idx, (key, link, prompt_text) in enumerate(prompts):
            if idx != 0:
                await interaction.followup.send(prompt_text, ephemeral=False)
            msg = await bot.wait_for("message", timeout=300.0, check=check)
            collected[key] = msg.content
    except asyncio.TimeoutError:
        return
    YELLOW = 0xFFFF00
    try:
        if "phone" in collected:
            embed = discord.Embed(description=collected["phone"] or "\u200b", color=YELLOW)
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(label="PHONE (APK)", url=phone_link, style=discord.ButtonStyle.secondary))
            await channel.send(embed=embed, view=view)
        if "pc" in collected:
            embed = discord.Embed(description=collected["pc"] or "\u200b", color=YELLOW)
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(label="PC DOWNLOAD", url=pc_link, style=discord.ButtonStyle.secondary))
            await channel.send(embed=embed, view=view)
        if "loader" in collected:
            embed = discord.Embed(description=collected["loader"] or "\u200b", color=YELLOW)
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(label="LOADER", url=loader_link, style=discord.ButtonStyle.secondary))
            await channel.send(embed=embed, view=view)
    except Exception:
        print("Failed to send one or more game embed messages", channel.id)

# ---------------- Lock / Unlock (persistent confirmation embed) ----------------
SUCCESS_EMOJI = "<:SCSuccess:1439236476616310844>"
GREEN_COLOR = 0x2ECC71

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

# ---------------- on_ready: final startup tasks ----------------
@bot.event
async def on_ready():
    # reload persisted data
    global panels, autoroles, applications
    panels = load_json_file(DB_PATH, panels)
    autoroles = load_json_file(AUTOROLES_PATH, autoroles)
    applications = load_json_file(APPLICATIONS_PATH, applications)

    # Ensure persistent views are registered (safe to call repeatedly)
    try:
        bot.add_view(ApplyButtonView())
        bot.add_view(ApplicationDecisionView())
    except Exception:
        pass

    # set presence/activity
    try:
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="⛄• Stumble Hour"))
    except Exception:
        pass

    # Sync commands
    try:
        if GUILD_ID:
            guild_obj = discord.Object(id=int(GUILD_ID))
            await tree.sync(guild=guild_obj)
        else:
            await tree.sync()
    except Exception as e:
        print("Failed to sync commands on_ready:", e)

    print(f"Bot ready. Logged in as {bot.user} (id: {bot.user.id})")

# ---------------- Run ----------------
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("Shutdown requested by user.")
    except Exception as e:
        print("Error starting bot:", e)