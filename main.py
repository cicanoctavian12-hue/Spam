import discord
from discord.ext import commands
import asyncio
import os
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

spam_tasks = {}
channel_tasks = {}

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} server(s)')

def is_owner():
    async def predicate(ctx):
        if ctx.guild is None:
            await ctx.send("This command can only be used in a server.")
            return False
        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send("Only the server owner can use this command.")
            return False
        return True
    return commands.check(predicate)

@bot.command(name='spam')
@is_owner()
async def spam(ctx, *, message: str):
    guild_id = ctx.guild.id
    
    if guild_id in spam_tasks and not spam_tasks[guild_id].done():
        await ctx.send("Spam is already running! Use !stopspam to stop it first.")
        return
    
    await ctx.send(f"Starting to send '{message}' 10 times...")
    
    async def spam_messages():
        try:
            for i in range(10):
                if guild_id not in spam_tasks or spam_tasks[guild_id].cancelled():
                    break
                await ctx.send(f"{message} ({i+1}/10)")
                await asyncio.sleep(1)
            await ctx.send("Finished sending 10 messages!")
        except Exception as e:
            await ctx.send(f"Error during spam: {e}")
    
    spam_tasks[guild_id] = asyncio.create_task(spam_messages())

@bot.command(name='stopspam')
@is_owner()
async def stopspam(ctx):
    guild_id = ctx.guild.id
    
    if guild_id in spam_tasks and not spam_tasks[guild_id].done():
        spam_tasks[guild_id].cancel()
        await ctx.send("Spam stopped!")
    else:
        await ctx.send("No spam is currently running.")

@bot.command(name='channels')
@is_owner()
async def channels(ctx):
    guild_id = ctx.guild.id
    
    if guild_id in channel_tasks and not channel_tasks[guild_id].done():
        await ctx.send("Channel creation is already running! Use !stopchannel to stop it first.")
        return
    
    await ctx.send("Starting to create 10 channels...")
    
    async def create_channels():
        try:
            for i in range(1, 11):
                if guild_id not in channel_tasks or channel_tasks[guild_id].cancelled():
                    break
                channel_name = f"wawa-{i}"
                await ctx.guild.create_text_channel(channel_name)
                await ctx.send(f"Created channel: {channel_name} ({i}/10)")
                await asyncio.sleep(1)
            await ctx.send("Finished creating 10 channels!")
        except discord.Forbidden:
            await ctx.send("I don't have permission to create channels!")
        except Exception as e:
            await ctx.send(f"Error during channel creation: {e}")
    
    channel_tasks[guild_id] = asyncio.create_task(create_channels())

@bot.command(name='stopchannel')
@is_owner()
async def stopchannel(ctx):
    guild_id = ctx.guild.id
    
    if guild_id in channel_tasks and not channel_tasks[guild_id].done():
        channel_tasks[guild_id].cancel()
        await ctx.send("Channel creation stopped!")
    else:
        await ctx.send("No channel creation is currently running.")

@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(
        title="Bot Commands",
        description="Available commands (Owner only):",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="!spam <message>",
        value="Sends a message 10 times with 1 second intervals",
        inline=False
    )
    embed.add_field(
        name="!stopspam",
        value="Stops the spam command",
        inline=False
    )
    embed.add_field(
        name="!channels",
        value="Creates 10 channels named 'wawa-1' through 'wawa-10'",
        inline=False
    )
    embed.add_field(
        name="!stopchannel",
        value="Stops the channel creation",
        inline=False
    )
    embed.set_footer(text="Only the server owner can use these commands")
    await ctx.send(embed=embed)

if __name__ == '__main__':
    keep_alive()
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found in environment variables!")
        print("Please add your Discord bot token to the Secrets tab.")
        exit(1)
    
    try:
        bot.run(token)
    except discord.LoginFailure:
        print("Error: Invalid Discord bot token!")
    except Exception as e:
        print(f"Error starting bot: {e}")
