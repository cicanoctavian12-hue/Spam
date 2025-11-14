import os
import re
import json
import asyncio
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

COLOR_MAP = {
    "red": 0xFF0000, "blue": 0x0000FF, "green": 0x00FF00, "yellow": 0xFFFF00,
    "orange": 0xFFA500, "purple": 0x800080, "pink": 0xFFC0CB, "black": 0x000000,
    "white": 0xFFFFFF, "grey": 0x808080, "gray": 0x808080, "teal": 0x008080,
    "gold": 0xFFD700, "default": 0x00AE86
}
def parse_color(value: str) -> int:
    if not value:
        raise ValueError("No color provided")
    v = value.strip().lower()
    if v in COLOR_MAP:
        return COLOR_MAP[v]
    if v.startswith("#"): v = v[1:]
    if v.startswith("0x"): v = v[2:]
    if re.fullmatch(r"[0-9a-f]{6}", v):
        return int(v, 16)
    if v.isdigit():
        iv = int(v)
        if 0 <= iv <= 0xFFFFFF:
            return iv
    raise ValueError("Invalid color format. Use a color name (red) or hex (#ff0000).")

def is_valid_url(u: str) -> bool:
    return isinstance(u, str) and (u.startswith("http://") or u.startswith("https://"))

# ---------------- Startup sync ----------------
@bot.event
async def on_ready():
    global panels, autoroles
    panels = load_json_file(DB_PATH, [])
    autoroles = load_json_file(AUTOROLES_PATH, {})
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

# ---------------- /embed slash command (existing) ----------------
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

# ---------------- /game slash command (interactive, user-provided text only) ----------------
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
    # Ensure invoker can use commands
    if not interaction.user.guild_permissions.send_messages:
        await interaction.response.send_message("You don't have permission to use this.", ephemeral=True)
        return

    # Validate URLs if provided
    for name, link in (("phone", phone_link), ("pc", pc_link), ("loader", loader_link)):
        if link and not is_valid_url(link):
            await interaction.response.send_message(f"{name}_link must be a valid http(s) URL.", ephemeral=True)
            return

    await interaction.response.send_message(
        "Creating game/info embed. I will prompt you for each section here. For each prompt, the FIRST message you send will be used as that section's text.",
        ephemeral=False
    )

    def check(m: discord.Message):
        return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

    try:
        # Title
        await interaction.followup.send("1) Enter the TITLE for the panel (first message you send will be used):", ephemeral=False)
        title_msg = await bot.wait_for("message", timeout=300.0, check=check)
        title_text = title_msg.content.strip()

        # Last updated (optional)
        await interaction.followup.send("2) Enter 'Last Updated' text (or send '-' to skip):", ephemeral=False)
        lu_msg = await bot.wait_for("message", timeout=180.0, check=check)
        last_updated = None if lu_msg.content.strip() == "-" else lu_msg.content.strip()

        # Main block (first required content block)
        await interaction.followup.send("3) Enter the MAIN block text (this can contain multiple lines/markdown):", ephemeral=False)
        main_msg = await bot.wait_for("message", timeout=300.0, check=check)
        main_block = main_msg.content

        # Optional section 2
        await interaction.followup.send("4) Do you want a SECOND block/section? Reply 'yes' or 'no' (first message counts):", ephemeral=False)
        resp2 = await bot.wait_for("message", timeout=120.0, check=check)
        add_section2 = resp2.content.strip().lower() in ("yes", "y", "true")
        section2_text = None
        if add_section2:
            await interaction.followup.send("Enter the SECOND block text (first message will be used):", ephemeral=False)
            s2 = await bot.wait_for("message", timeout=300.0, check=check)
            section2_text = s2.content

        # Optional notes/warning block
        await interaction.followup.send("5) Do you want a NOTES/WARNING block? Reply 'yes' or 'no' (first message counts):", ephemeral=False)
        resp_notes = await bot.wait_for("message", timeout=120.0, check=check)
        add_notes = resp_notes.content.strip().lower() in ("yes", "y", "true")
        notes_text = None
        if add_notes:
            await interaction.followup.send("Enter the NOTES/WARNING text (first message will be used):", ephemeral=False)
            notes_msg = await bot.wait_for("message", timeout=300.0, check=check)
            notes_text = notes_msg.content

        # For each provided link ask for the section text (first message used)
        phone_text = None
        if phone_link:
            await interaction.followup.send("You provided a phone link. Enter the text to display above the phone button (first message used):", ephemeral=False)
            try:
                ph = await bot.wait_for("message", timeout=300.0, check=check)
                phone_text = ph.content
            except asyncio.TimeoutError:
                phone_text = None

        pc_text = None
        if pc_link:
            await interaction.followup.send("You provided a PC link. Enter the text to display above the PC button (first message used):", ephemeral=False)
            try:
                pc = await bot.wait_for("message", timeout=300.0, check=check)
                pc_text = pc.content
            except asyncio.TimeoutError:
                pc_text = None

        loader_text = None
        if loader_link:
            await interaction.followup.send("You provided a loader link. Enter the text to display above the loader button (first message used):", ephemeral=False)
            try:
                ld = await bot.wait_for("message", timeout=300.0, check=check)
                loader_text = ld.content
            except asyncio.TimeoutError:
                loader_text = None

    except asyncio.TimeoutError:
        await interaction.followup.send("Timed out waiting for your responses. Please run the command again.", ephemeral=True)
        return

    # Build embed using ONLY the user's provided text (no hard-coded screenshot text)
    EMBED_COLOR = 0xFFD54F  # yellow-ish default
    embed = discord.Embed(title=title_text or "\u200b", color=EMBED_COLOR)
    if last_updated:
        embed.add_field(name="\u200b", value=f"_Last Updated: {last_updated}_", inline=False)

    # Main block: preserve user's formatting
    embed.add_field(name="\u200b", value=main_block or "\u200b", inline=False)

    if section2_text:
        embed.add_field(name="\u200b", value=section2_text, inline=False)

    if notes_text:
        embed.add_field(name="\u200b", value=notes_text, inline=False)

    # View with URL buttons (URL buttons are persistent links, they work after bot restarts)
    view = discord.ui.View(timeout=None)

    # Button labels updated to be clear to users about what they download
    if phone_text:
        embed.add_field(name="📱", value=phone_text, inline=False)
        view.add_item(discord.ui.Button(label="PHONE (APK)", url=phone_link, style=discord.ButtonStyle.secondary))

    if pc_text:
        embed.add_field(name="💻", value=pc_text, inline=False)
        view.add_item(discord.ui.Button(label="PC DOWNLOAD", url=pc_link, style=discord.ButtonStyle.secondary))

    if loader_text:
        embed.add_field(name="🧩", value=loader_text, inline=False)
        view.add_item(discord.ui.Button(label="LOADER", url=loader_link, style=discord.ButtonStyle.secondary))

    # Thumbnail: use guild icon if available; user text only otherwise
    try:
        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
    except Exception:
        pass

    # Send the embed to the specified channel
    try:
        await channel.send(embed=embed, view=view)
        await interaction.followup.send(f"Panel sent to {channel.mention}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("I don't have permission to send messages or embeds in the target channel.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Failed to send embed: {e}", ephemeral=True)

# ---------------- Run ----------------
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("Shutdown requested by user.")
    except Exception as e:
        print("Error starting bot:", e)