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

if not TOKEN:
    print("ERROR: TOKEN environment variable not set. Exiting.")
    raise SystemExit(1)

# Intents
intents = discord.Intents.default()
intents.guilds = True
intents.members = True  # required to add/remove roles and fetch members in raw events
intents.messages = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)
# alias to app command tree
tree = bot.tree

# ---------------- Persistence ----------------
def load_db():
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
        return []
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("Failed to load DB, resetting:", e)
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
        return []

def save_db(data):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

panels = []  # list of saved panels

# ---------------- Emoji parsing ----------------
# Match <a:name:id> or <:name:id>
CUSTOM_EMOJI_RE = re.compile(r"^<(a?):([A-Za-z0-9_~]+):([0-9]+)>$")
# Match name:id (no brackets)
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

# ---------------- Ready & sync ----------------
@bot.event
async def on_ready():
    global panels
    panels = load_db()
    print(f"Logged in as {bot.user} (id: {bot.user.id}). Loaded {len(panels)} panel(s) from {DB_PATH}.")
    # Sync commands to a test guild if provided (fast)
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

# ---------------- Auto role on join ----------------
AUTO_ROLE_ID = 1436385898110517402  # role to give when someone joins

@bot.event
async def on_member_join(member: discord.Member):
    """
    Auto-assign a role when a member joins.
    Ensure the bot has Manage Roles and its highest role is above AUTO_ROLE_ID.
    """
    try:
        guild = member.guild
        role = guild.get_role(AUTO_ROLE_ID)
        if role is None:
            print(f"[on_member_join] Role id {AUTO_ROLE_ID} not found in guild {guild.id}.")
            return
        # Try to add role
        await member.add_roles(role, reason="Auto role on join")
        print(f"[on_member_join] Assigned role {role.name} ({role.id}) to {member} on join.")
    except Exception as e:
        print(f"[on_member_join] Failed to assign role {AUTO_ROLE_ID} to {member.id}: {e}")

# ---------------- Reaction handlers (raw events) ----------------
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    # Ignore bot reactions
    if payload.user_id == bot.user.id:
        return
    try:
        if payload.guild_id is None:
            return
        # Find matching panel
        panel = next((p for p in panels if p["message_id"] == str(payload.message_id) and p["guild_id"] == str(payload.guild_id)), None)
        if not panel:
            return

        # Determine payload emoji identity
        emoji_id = payload.emoji.id  # None or int
        emoji_name = payload.emoji.name  # string (unicode or name of custom)

        # Find entry in panel
        matched = None
        for e in panel.get("entries", []):
            if e.get("type") == "custom":
                # Compare by id (best)
                try:
                    if emoji_id is not None and int(e.get("id")) == int(emoji_id):
                        matched = e
                        break
                    # fallback: sometimes name matches (rare)
                    if emoji_name and str(e.get("name")) == str(emoji_name):
                        matched = e
                        break
                except Exception:
                    continue
            else:
                # unicode stored by name/string
                if emoji_id is None and e.get("name") == emoji_name:
                    matched = e
                    break
        if not matched:
            return

        # Fetch guild and member
        guild = bot.get_guild(payload.guild_id)
        if not guild:
            try:
                guild = await bot.fetch_guild(payload.guild_id)
            except Exception:
                return

        try:
            member = await guild.fetch_member(payload.user_id)
        except Exception:
            member = guild.get_member(payload.user_id)
        if not member:
            return

        # Fetch role
        role_id = int(matched.get("role_id"))
        role = guild.get_role(role_id)
        if not role:
            print(f"[on_raw_reaction_add] Role id {role_id} not found in guild {guild.id}.")
            return

        # Add role if missing
        if role.id not in [r.id for r in member.roles]:
            try:
                await member.add_roles(role, reason=f"Reaction role (message {panel['message_id']})")
                print(f"[on_raw_reaction_add] Added role {role.name} ({role.id}) to member {member} for reaction on message {panel['message_id']}.")
            except Exception as e:
                print(f"[on_raw_reaction_add] Failed to add role {role_id} to {member.id}: {e}")
    except Exception as e:
        print("Error in on_raw_reaction_add:", e)

@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    # Ignore bot
    if payload.user_id == bot.user.id:
        return
    try:
        if payload.guild_id is None:
            return
        panel = next((p for p in panels if p["message_id"] == str(payload.message_id) and p["guild_id"] == str(payload.guild_id)), None)
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

        guild = bot.get_guild(payload.guild_id)
        if not guild:
            try:
                guild = await bot.fetch_guild(payload.guild_id)
            except Exception:
                return

        try:
            member = await guild.fetch_member(payload.user_id)
        except Exception:
            member = guild.get_member(payload.user_id)
        if not member:
            return

        role_id = int(matched.get("role_id"))
        role = guild.get_role(role_id)
        if not role:
            print(f"[on_raw_reaction_remove] Role id {role_id} not found in guild {guild.id}.")
            return

        if role.id in [r.id for r in member.roles]:
            try:
                await member.remove_roles(role, reason=f"Reaction role removal (message {panel['message_id']})")
                print(f"[on_raw_reaction_remove] Removed role {role.name} ({role.id}) from member {member} for reaction remove on message {panel['message_id']}.")
            except Exception as e:
                print(f"[on_raw_reaction_remove] Failed to remove role {role_id} from {member.id}: {e}")
    except Exception as e:
        print("Error in on_raw_reaction_remove:", e)

# ---------------- /role-panel command ----------------
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
    # Permission check: require Manage Roles
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("You need the Manage Roles permission to create a role panel.", ephemeral=True)
        return

    # collect pairs
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

    # Build embed (no "requested by" footer)
    embed = discord.Embed(description=text, color=0x00AE86)
    # set guild icon as thumbnail (right side)
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

    # React with emojis (best-effort)
    for parsed, role in pairs:
        try:
            if parsed["type"] == "custom":
                try:
                    p = discord.PartialEmoji(name=parsed["name"], id=int(parsed["id"]), animated=bool(parsed.get("animated", False)))
                    await sent.add_reaction(p)
                except Exception:
                    # fallback to raw string like "<:name:id>" or "<a:name:id>"
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

    # Store mapping in DB
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
    save_db(panels)
    await interaction.followup.send("Role panel created.", ephemeral=True)

# ---------------- /embed command ----------------
@bot.tree.command(name="embed", description="Create a simple embed with text and optional picture URL.")
@discord.app_commands.describe(
    text="Text for the embed (supports server emojis and up to Discord embed limit)",
    picture="Optional direct image URL to show under the embed"
)
async def create_embed(interaction: discord.Interaction, text: str, picture: str = None):
    """
    /embed text:<required> picture:<optional url>
    - text: the embed description (max 4096 chars)
    - picture: optional URL to show as image under the embed
    """
    # permission: allow anyone to use? If you want admin-only, check guild_permissions here.
    # We'll allow any user to create the embed in the channel the command is used.
    # Validate length
    if text is None or text.strip() == "":
        await interaction.response.send_message("You must provide text for the embed.", ephemeral=True)
        return
    if len(text) > 4096:
        await interaction.response.send_message("Text is too long for an embed (limit 4096 characters).", ephemeral=True)
        return

    # Basic picture validation (optional). Accept empty/None.
    if picture:
        picture = picture.strip()
        if not (picture.startswith("http://") or picture.startswith("https://")):
            await interaction.response.send_message("Picture must be a valid URL starting with http:// or https://", ephemeral=True)
            return

    embed = discord.Embed(description=text, color=0x00AE86)
    # Allow using server emojis by leaving text raw (Discord will render them if valid)
    if picture:
        embed.set_image(url=picture)

    # Send embed in channel
    try:
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        # If immediate response fails, try fallback
        try:
            await interaction.followup.send(embed=embed)
        except Exception as exc:
            await interaction.response.send_message("Failed to send embed: " + str(exc), ephemeral=True)

# ---------------- Run ----------------
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("Shutdown requested by user.")
    except Exception as e:
        print("Error starting bot:", e)