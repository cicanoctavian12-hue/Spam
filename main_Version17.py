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

# ---------------- Lock / Unlock commands ----------------
@bot.command(name="lock")
@commands.has_guild_permissions(manage_channels=True)
async def lock(ctx, *allowed_roles: discord.Role):
    """
    Usage:
      !lock               -> lock the current channel for @everyone
      !lock @Role1 @Role2 -> lock channel for @everyone but allow Role1 and Role2 to send messages
    """
    try:
        # Attempt to delete command message for cleanliness (best-effort)
        try:
            await ctx.message.delete()
        except Exception:
            pass

        channel = ctx.channel
        guild = ctx.guild
        everyone = guild.default_role

        # Preserve read_messages permission if set
        current_overwrite = channel.overwrites_for(everyone)
        read_perm = current_overwrite.read_messages if current_overwrite.read_messages is not None else True

        # Deny send_messages for @everyone
        await channel.set_permissions(everyone, send_messages=False, read_messages=read_perm)

        # Allow listed roles to send messages
        allowed_mentions = []
        for role in allowed_roles:
            role_overwrite = channel.overwrites_for(role)
            await channel.set_permissions(role, send_messages=True, read_messages=role_overwrite.read_messages)
            allowed_mentions.append(role.mention)

        # Confirmation message
        mention_text = ", ".join(allowed_mentions) if allowed_mentions else "no specific roles"
        await ctx.send(f"✅ Channel successfully locked. Allowed: {mention_text}", delete_after=10)
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
    Removes explicit send_messages overwrites in the current channel (restores default).
    """
    try:
        try:
            await ctx.message.delete()
        except Exception:
            pass

        channel = ctx.channel

        # Remove explicit send_messages overwrites for all targets
        # Iterate through current overwrites and clear send_messages
        for target, overwrite in list(channel.overwrites.items()):
            if overwrite.send_messages is not None:
                new_overwrite = discord.PermissionOverwrite(**{k: getattr(overwrite, k) for k in overwrite._values if k != 'send_messages'})
                # Setting send_messages to None (by not including) - set_permissions overwrites with new_overwrite
                await channel.set_permissions(target, overwrite=new_overwrite)

        # Ensure @everyone send_messages is None
        everyone = ctx.guild.default_role
        eo = channel.overwrites_for(everyone)
        if eo.send_messages is not None:
            eo.send_messages = None
            await channel.set_permissions(everyone, overwrite=eo)

        await ctx.send("✅ Channel successfully unlocked.", delete_after=10)
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
        # parse_color not used here; reusing earlier helper if needed
        pass
    except Exception:
        pass
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
    embed = discord.Embed(description=content, color=0x00AE86)
    if picture:
        embed.set_image(url=picture)
    try:
        await channel.send(embed=embed)
        await interaction.followup.send(f"Embed sent to {channel.mention}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("I don't have permission to send embeds in the target channel.", ephemeral=True)

# ---------------- /game slash command (updated: each embed its own message + button, yellow color) ----------------
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

    # Build list of selected options
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

    # Ask prompts one-by-one; each prompt is exactly the short question requested.
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
        # silent on timeout per your "no extra text" preference
        return

    # For each selected option send ONE message containing THAT embed and its own button under it.
    YELLOW = 0xFFFF00
    try:
        # Phone
        if "phone" in collected:
            embed = discord.Embed(description=collected["phone"] or "\u200b", color=YELLOW)
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(label="PHONE (APK)", url=phone_link, style=discord.ButtonStyle.secondary))
            await channel.send(embed=embed, view=view)

        # PC
        if "pc" in collected:
            embed = discord.Embed(description=collected["pc"] or "\u200b", color=YELLOW)
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(label="PC DOWNLOAD", url=pc_link, style=discord.ButtonStyle.secondary))
            await channel.send(embed=embed, view=view)

        # Loader
        if "loader" in collected:
            embed = discord.Embed(description=collected["loader"] or "\u200b", color=YELLOW)
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(label="LOADER", url=loader_link, style=discord.ButtonStyle.secondary))
            await channel.send(embed=embed, view=view)

        # Per your request: do not send any additional confirmation text.
    except Exception:
        # silent failure (but log to console)
        print("Failed to send one or more game embed messages", channel.id)

# ---------------- Run ----------------
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("Shutdown requested by user.")
    except Exception as e:
        print("Error starting bot:", e)