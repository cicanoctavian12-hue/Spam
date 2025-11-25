import discord
from discord import app_commands
from datetime import datetime, timezone

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


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

    unix_time = int(datetime.now(tz=timezone.utc).timestamp())

    embed = discord.Embed(
        title="Stumble Hour Downloads",
        color=discord.Color.yellow()
    )

    embed.add_field(
        name="",
        value=(
            f"⏱️ Last Updated: <t:{unix_time}:R>\n"
            f"🔹 Stumble Guys build version: {sg_build_vers}\n"
            f"🔸 Stumble Hour version: {stumble_hour_build_vers}"
        ),
        inline=False
    )

    embed.add_field(
        name="📱 Phone download",
        value="<:BF:1442503402968842371> Android",
        inline=False
    )

    embed.add_field(
        name="💻 Pc download",
        value="<:BF:1442503402968842371> Game folder",
        inline=False
    )

    embed.add_field(
        name="<:sg_check:1442516721658495056> Loader DLL",
        value="<:BF:1442503402968842371> Pc loader",
        inline=False
    )

    view = discord.ui.View()
    view.add_item(discord.ui.Button(
        label="Phone Download",
        style=discord.ButtonStyle.link,
        url=phone_link
    ))
    view.add_item(discord.ui.Button(
        label="PC Download",
        style=discord.ButtonStyle.link,
        url=pc_link
    ))
    view.add_item(discord.ui.Button(
        label="Loader DLL",
        style=discord.ButtonStyle.link,
        url=dll_link
    ))

    await interaction.response.send_message(embed=embed, view=view)


@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot connected as {client.user}")


client.run("YOUR_BOT_TOKEN")
