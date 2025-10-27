import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
import os
import random
import asyncio
import time
import json
import re
from datetime import datetime, timedelta

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

TRIVIA_QUESTIONS = [
    {"q": "What is the chemical symbol for gold?", "a": "au"},
    {"q": "In which year did World War I begin?", "a": "1914"},
    {"q": "What is the largest ocean on Earth?", "a": "pacific"},
    {"q": "Who wrote the novel '1984'?", "a": "george orwell"},
    {"q": "What is the capital city of Australia?", "a": "canberra"},
    {"q": "How many elements are in the periodic table?", "a": "118"},
    {"q": "What is the smallest prime number?", "a": "2"},
    {"q": "Which planet is known as the 'Morning Star'?", "a": "venus"},
    {"q": "What is the speed of light in vacuum (in km/s)?", "a": "300000"},
    {"q": "Who painted the Mona Lisa?", "a": "leonardo da vinci"},
    {"q": "What is the hardest natural substance on Earth?", "a": "diamond"},
    {"q": "In which year did the Titanic sink?", "a": "1912"},
    {"q": "What is the smallest country in the world?", "a": "vatican city"},
    {"q": "Who discovered penicillin?", "a": "alexander fleming"},
    {"q": "What is the largest mammal on Earth?", "a": "blue whale"},
    {"q": "How many bones are in the adult human body?", "a": "206"},
    {"q": "What is the capital of Iceland?", "a": "reykjavik"},
    {"q": "Who wrote 'Romeo and Juliet'?", "a": "william shakespeare"},
    {"q": "What is the chemical formula for water?", "a": "h2o"},
    {"q": "In which year did the Berlin Wall fall?", "a": "1989"},
    {"q": "What is the tallest mountain in the world?", "a": "mount everest"},
    {"q": "Who invented the telephone?", "a": "alexander graham bell"},
    {"q": "What is the largest planet in our solar system?", "a": "jupiter"},
    {"q": "How many chromosomes do humans have?", "a": "46"},
    {"q": "What is the boiling point of water in Celsius?", "a": "100"},
    {"q": "Who was the first person to walk on the moon?", "a": "neil armstrong"},
    {"q": "What is the smallest ocean on Earth?", "a": "arctic"},
    {"q": "In which year did Christopher Columbus discover America?", "a": "1492"},
    {"q": "What is the currency of Japan?", "a": "yen"},
    {"q": "Who wrote 'Pride and Prejudice'?", "a": "jane austen"},
    {"q": "What is the most abundant gas in Earth's atmosphere?", "a": "nitrogen"},
    {"q": "How many sides does a hexagon have?", "a": "6"},
    {"q": "What is the capital of Brazil?", "a": "brasilia"},
    {"q": "Who painted 'The Starry Night'?", "a": "vincent van gogh"},
    {"q": "What is the freezing point of water in Fahrenheit?", "a": "32"},
    {"q": "In which year did World War II end?", "a": "1945"},
    {"q": "What is the largest desert in the world?", "a": "sahara"},
    {"q": "Who developed the theory of relativity?", "a": "albert einstein"},
    {"q": "What is the smallest unit of life?", "a": "cell"},
    {"q": "How many players are on a soccer team?", "a": "11"},
    {"q": "What is the capital of Egypt?", "a": "cairo"},
    {"q": "Who wrote 'To Kill a Mockingbird'?", "a": "harper lee"},
    {"q": "What is the atomic number of carbon?", "a": "6"},
    {"q": "In which year did the French Revolution begin?", "a": "1789"},
    {"q": "What is the longest river in the world?", "a": "nile"},
    {"q": "Who invented the light bulb?", "a": "thomas edison"},
    {"q": "What is the largest organ in the human body?", "a": "skin"},
    {"q": "How many teeth does an adult human have?", "a": "32"},
    {"q": "What is the capital of Canada?", "a": "ottawa"},
    {"q": "Who wrote 'The Great Gatsby'?", "a": "f scott fitzgerald"},
    {"q": "What is the chemical symbol for sodium?", "a": "na"},
    {"q": "In which year did the American Civil War end?", "a": "1865"},
    {"q": "What is the largest island in the world?", "a": "greenland"},
    {"q": "Who discovered gravity?", "a": "isaac newton"},
    {"q": "What is the fastest land animal?", "a": "cheetah"},
    {"q": "How many continents are there?", "a": "7"},
    {"q": "What is the capital of Russia?", "a": "moscow"},
    {"q": "Who wrote 'The Catcher in the Rye'?", "a": "j d salinger"},
    {"q": "What is the atomic number of oxygen?", "a": "8"},
    {"q": "In which year was the United Nations founded?", "a": "1945"},
    {"q": "What is the deepest ocean trench?", "a": "mariana trench"},
    {"q": "Who painted 'The Last Supper'?", "a": "leonardo da vinci"},
    {"q": "What is the largest bird in the world?", "a": "ostrich"},
    {"q": "How many strings does a standard guitar have?", "a": "6"},
    {"q": "What is the capital of Spain?", "a": "madrid"},
    {"q": "Who wrote 'Moby Dick'?", "a": "herman melville"},
    {"q": "What is the chemical symbol for iron?", "a": "fe"},
    {"q": "In which year did the Soviet Union collapse?", "a": "1991"},
    {"q": "What is the largest lake in the world?", "a": "caspian sea"},
    {"q": "Who invented the printing press?", "a": "johannes gutenberg"},
    {"q": "What is the main component of the Sun?", "a": "hydrogen"},
    {"q": "How many hearts does an octopus have?", "a": "3"},
    {"q": "What is the capital of India?", "a": "new delhi"},
    {"q": "Who wrote 'War and Peace'?", "a": "leo tolstoy"},
    {"q": "What is the chemical symbol for silver?", "a": "ag"},
    {"q": "In which year was the Magna Carta signed?", "a": "1215"},
    {"q": "What is the largest volcano in the world?", "a": "mauna loa"},
    {"q": "Who discovered DNA structure?", "a": "watson and crick"},
    {"q": "What is the longest bone in the human body?", "a": "femur"},
    {"q": "How many moons does Mars have?", "a": "2"},
    {"q": "What is the capital of China?", "a": "beijing"},
    {"q": "Who wrote 'One Hundred Years of Solitude'?", "a": "gabriel garcia marquez"},
    {"q": "What is the chemical symbol for mercury?", "a": "hg"},
    {"q": "In which year did the first moon landing occur?", "a": "1969"},
    {"q": "What is the largest reef system in the world?", "a": "great barrier reef"},
    {"q": "Who invented the airplane?", "a": "wright brothers"},
    {"q": "What is the most common blood type?", "a": "o positive"},
    {"q": "How many keys are on a standard piano?", "a": "88"},
    {"q": "What is the capital of Germany?", "a": "berlin"},
    {"q": "Who wrote 'The Odyssey'?", "a": "homer"},
    {"q": "What is the chemical symbol for potassium?", "a": "k"},
    {"q": "In which year did the Black Death peak in Europe?", "a": "1348"},
    {"q": "What is the largest rainforest in the world?", "a": "amazon"},
    {"q": "Who discovered radioactivity?", "a": "marie curie"},
    {"q": "What is the powerhouse of the cell?", "a": "mitochondria"},
    {"q": "How many valves does the human heart have?", "a": "4"},
    {"q": "What is the capital of Italy?", "a": "rome"},
    {"q": "Who wrote 'Crime and Punishment'?", "a": "fyodor dostoevsky"},
    {"q": "What is the chemical symbol for copper?", "a": "cu"},
    {"q": "In which year did the Renaissance begin?", "a": "1300"},
    {"q": "What is the largest canyon in the world?", "a": "grand canyon"},
    {"q": "Who invented the steam engine?", "a": "james watt"},
    {"q": "What is the rarest blood type?", "a": "ab negative"},
    {"q": "How many chambers does the human heart have?", "a": "4"},
    {"q": "What is the capital of France?", "a": "paris"},
    {"q": "Who wrote 'The Divine Comedy'?", "a": "dante alighieri"},
    {"q": "What is the chemical symbol for lead?", "a": "pb"},
    {"q": "In which year was the Eiffel Tower completed?", "a": "1889"},
    {"q": "What is the largest waterfall in the world?", "a": "angel falls"},
    {"q": "Who discovered America (from European perspective)?", "a": "christopher columbus"},
    {"q": "What is the process by which plants make food?", "a": "photosynthesis"},
    {"q": "How many planets are in our solar system?", "a": "8"},
    {"q": "What is the capital of Japan?", "a": "tokyo"},
    {"q": "Who wrote 'Don Quixote'?", "a": "miguel de cervantes"},
    {"q": "What is the chemical symbol for helium?", "a": "he"},
    {"q": "In which year was the Declaration of Independence signed?", "a": "1776"},
    {"q": "What is the largest bay in the world?", "a": "hudson bay"},
    {"q": "Who invented the radio?", "a": "guglielmo marconi"},
    {"q": "What is the study of earthquakes called?", "a": "seismology"},
    {"q": "How many states are in the USA?", "a": "50"},
    {"q": "What is the capital of South Korea?", "a": "seoul"},
    {"q": "Who wrote 'The Iliad'?", "a": "homer"},
    {"q": "What is the chemical symbol for tin?", "a": "sn"},
    {"q": "In which year did the Industrial Revolution begin?", "a": "1760"},
    {"q": "What is the largest peninsula in the world?", "a": "arabian peninsula"},
    {"q": "Who discovered the electron?", "a": "j j thomson"},
    {"q": "What is the study of life called?", "a": "biology"},
    {"q": "How many time zones are there in Russia?", "a": "11"},
    {"q": "What is the capital of Mexico?", "a": "mexico city"},
    {"q": "Who wrote 'Les Misérables'?", "a": "victor hugo"},
    {"q": "What is the chemical symbol for platinum?", "a": "pt"},
    {"q": "In which year was the printing press invented?", "a": "1440"},
    {"q": "What is the largest gulf in the world?", "a": "gulf of mexico"},
    {"q": "Who discovered the neutron?", "a": "james chadwick"},
    {"q": "What is the study of the weather called?", "a": "meteorology"},
    {"q": "How many rings does Saturn have?", "a": "7"},
    {"q": "What is the capital of Argentina?", "a": "buenos aires"},
    {"q": "Who wrote 'Anna Karenina'?", "a": "leo tolstoy"},
    {"q": "What is the chemical symbol for zinc?", "a": "zn"},
    {"q": "In which year did the Cold War end?", "a": "1991"},
    {"q": "What is the largest sea in the world?", "a": "philippine sea"},
    {"q": "Who discovered X-rays?", "a": "wilhelm roentgen"},
    {"q": "What is the study of stars and planets called?", "a": "astronomy"},
    {"q": "How many bones are in the human skull?", "a": "22"},
    {"q": "What is the capital of Turkey?", "a": "ankara"},
    {"q": "Who wrote 'Brave New World'?", "a": "aldous huxley"}
]

HANGMAN_WORDS = [
    "PYTHON", "JAVASCRIPT", "PROGRAMMING", "COMPUTER", "KEYBOARD", "ALGORITHM",
    "DATABASE", "INTERNET", "SOFTWARE", "HARDWARE", "NETWORK", "SECURITY",
    "ENCRYPTION", "FIREWALL", "PROTOCOL", "BANDWIDTH", "ROUTER", "SERVER",
    "DEVELOPER", "ENGINEER", "FUNCTION", "VARIABLE", "CONSTANT", "BOOLEAN",
    "INTEGER", "STRING", "ARRAY", "OBJECT", "CLASS", "METHOD",
    "INTERFACE", "INHERITANCE", "POLYMORPHISM", "ABSTRACTION", "ENCAPSULATION", "MODULE",
    "PACKAGE", "LIBRARY", "FRAMEWORK", "COMPILER", "DEBUGGER", "REPOSITORY",
    "BRANCH", "COMMIT", "MERGE", "CONFLICT", "VERSION", "RELEASE",
    "DEPLOYMENT", "PRODUCTION", "STAGING", "TESTING", "AUTOMATION", "CONTINUOUS",
    "INTEGRATION", "PIPELINE", "CONTAINER", "DOCKER", "KUBERNETES", "MICROSERVICE",
    "ARCHITECTURE", "DESIGN", "PATTERN", "SINGLETON", "FACTORY", "OBSERVER",
    "STRATEGY", "DECORATOR", "ADAPTER", "FACADE", "PROXY", "COMPOSITE",
    "COMMAND", "ITERATOR", "MEDIATOR", "MEMENTO", "STATE", "TEMPLATE",
    "VISITOR", "CHAIN", "FLYWEIGHT", "PROTOTYPE", "BUILDER", "BRIDGE",
    "BLOCKCHAIN", "CRYPTOCURRENCY", "BITCOIN", "ETHEREUM", "MINING", "WALLET",
    "TRANSACTION", "LEDGER", "CONSENSUS", "DECENTRALIZED", "DISTRIBUTED", "PEER",
    "ARTIFICIAL", "INTELLIGENCE", "MACHINE", "LEARNING", "NEURAL", "NETWORK",
    "DEEP", "TRAINING", "MODEL", "DATASET", "FEATURE", "CLASSIFICATION",
    "REGRESSION", "CLUSTERING", "SUPERVISED", "UNSUPERVISED", "REINFORCEMENT", "BACKPROPAGATION",
    "GRADIENT", "DESCENT", "OPTIMIZATION", "OVERFITTING", "UNDERFITTING", "VALIDATION",
    "ACCURACY", "PRECISION", "RECALL", "CONFUSION", "MATRIX", "CROSS",
    "HYPERPARAMETER", "ACTIVATION", "SIGMOID", "RELU", "TANH", "SOFTMAX",
    "CONVOLUTIONAL", "RECURRENT", "TRANSFORMER", "ATTENTION", "EMBEDDING", "TOKENIZATION",
    "NATURAL", "LANGUAGE", "PROCESSING", "SENTIMENT", "ANALYSIS", "CLASSIFICATION",
    "EXTRACTION", "RECOGNITION", "GENERATION", "TRANSLATION", "SUMMARIZATION", "QUESTION",
    "ANSWERING", "CHATBOT", "DIALOGUE", "CONTEXT", "SEMANTIC", "SYNTACTIC",
    "PARSING", "TAGGING", "DEPENDENCY", "CONSTITUENCY", "MORPHOLOGY", "PHONOLOGY",
    "CYBERSECURITY", "VULNERABILITY", "EXPLOIT", "MALWARE", "VIRUS", "TROJAN",
    "RANSOMWARE", "PHISHING", "SPOOFING", "INJECTION", "OVERFLOW", "BREACH",
    "AUTHENTICATION", "AUTHORIZATION", "CERTIFICATE", "CRYPTOGRAPHY", "HASH", "SALT",
    "PEPPER", "TOKEN", "SESSION", "COOKIE", "CROSS", "SITE",
    "SCRIPTING", "REQUEST", "FORGERY", "CLICKJACKING", "HIJACKING", "SNIFFING",
    "DATABASE", "RELATIONAL", "NOSQL", "MONGODB", "POSTGRESQL", "MYSQL",
    "SQLITE", "REDIS", "CASSANDRA", "ELASTICSEARCH", "SCHEMA", "TABLE",
    "COLUMN", "ROW", "INDEX", "PRIMARY", "FOREIGN", "CONSTRAINT"
]

warnings_data = {}
economy_data = {}
shop_items = {}
buy_channel_id = {}

CURRENCY_EMOJI = "<:mybobaaa:1429521333896614000>"
DAILY_AMOUNT = 1000

def load_economy():
    global economy_data
    try:
        with open('economy.json', 'r') as f:
            economy_data = json.load(f)
    except FileNotFoundError:
        economy_data = {}

def save_economy():
    with open('economy.json', 'w') as f:
        json.dump(economy_data, f, indent=4)

def load_shop():
    global shop_items
    try:
        with open('shop.json', 'r') as f:
            shop_items = json.load(f)
    except FileNotFoundError:
        shop_items = {}

def save_shop():
    with open('shop.json', 'w') as f:
        json.dump(shop_items, f, indent=4)

def load_buy_channel():
    global buy_channel_id
    try:
        with open('buy_channel.json', 'r') as f:
            buy_channel_id = json.load(f)
    except FileNotFoundError:
        buy_channel_id = {}

def save_buy_channel():
    with open('buy_channel.json', 'w') as f:
        json.dump(buy_channel_id, f, indent=4)

def get_balance(guild_id, user_id):
    guild_id = str(guild_id)
    user_id = str(user_id)
    if guild_id not in economy_data:
        economy_data[guild_id] = {}
    if user_id not in economy_data[guild_id]:
        economy_data[guild_id][user_id] = {'balance': 0, 'last_daily': None}
    return economy_data[guild_id][user_id]['balance']

def add_balance(guild_id, user_id, amount):
    guild_id = str(guild_id)
    user_id = str(user_id)
    if guild_id not in economy_data:
        economy_data[guild_id] = {}
    if user_id not in economy_data[guild_id]:
        economy_data[guild_id][user_id] = {'balance': 0, 'last_daily': None}
    economy_data[guild_id][user_id]['balance'] += amount
    save_economy()
    return economy_data[guild_id][user_id]['balance']

def remove_balance(guild_id, user_id, amount):
    guild_id = str(guild_id)
    user_id = str(user_id)
    if guild_id not in economy_data:
        economy_data[guild_id] = {}
    if user_id not in economy_data[guild_id]:
        economy_data[guild_id][user_id] = {'balance': 0, 'last_daily': None}
    economy_data[guild_id][user_id]['balance'] -= amount
    save_economy()
    return economy_data[guild_id][user_id]['balance']

def load_warnings():
    global warnings_data
    try:
        with open('warnings.json', 'r') as f:
            warnings_data = json.load(f)
    except FileNotFoundError:
        warnings_data = {}

def save_warnings():
    with open('warnings.json', 'w') as f:
        json.dump(warnings_data, f, indent=4)

def remove_emojis(text):
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001F900-\U0001F9FF"
        u"\U0001FA70-\U0001FAFF"
        "]+", flags=re.UNICODE)
    text = emoji_pattern.sub('', text)
    text = re.sub(r'<:[^:]+:\d+>', '', text)
    text = re.sub(r'<a:[^:]+:\d+>', '', text)
    return text.strip()

@bot.event
async def on_ready():
    load_warnings()
    load_economy()
    load_shop()
    load_buy_channel()
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} slash command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} server(s)')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.content.startswith('!'):
        try:
            await bot.process_commands(message)
            await message.delete()
        except discord.Forbidden:
            await bot.process_commands(message)
        except Exception:
            await bot.process_commands(message)
    else:
        await bot.process_commands(message)

@bot.command(name='ping')
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f'Pong! 🏓 Latency: {latency}ms')

@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(
        title="🤖 Bot Commands",
        description="Here are all available commands:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="⚡ Basic",
        value="`!ping` - Bot latency\n`!help` - This message",
        inline=False
    )
    
    embed.add_field(
        name="🎮 Multiplayer Games",
        value="`!ttt [@user]` - Tic-Tac-Toe\n`!rps [@user]` - Rock Paper Scissors",
        inline=False
    )
    
    embed.add_field(
        name="🧩 Solo Games",
        value=(
            "`!hangman` - Guess the word\n"
            "`!trivia` - Trivia questions\n"
            "`!math` - Math problems\n"
            "`!wordguess` - Unscramble words\n"
            "`!guess` - Number guessing (1-100)\n"
            "`!memory` - Memory game\n"
            "`!typerace` - Typing test"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🎲 Fun Games",
        value="`!8ball <question>` - Magic 8-Ball\n`!wyr` - Would You Rather",
        inline=False
    )
    
    embed.add_field(
        name="🛡️ Moderation",
        value=(
            "`!ban <member> [reason]` - Ban member\n"
            "`!unban <user_id>` - Unban user\n"
            "`!mute <member> [duration] [reason]` - Mute member\n"
            "`!unmute <member>` - Unmute member\n"
            "`!lock` - Lock channel\n"
            "`!unlock` - Unlock channel\n"
            "`!warn <member> [reason]` - Warn member\n"
            "`!warnings <member>` - View warnings"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📢 Events",
        value="`!spamevent` - Start spam event\n`!stopspamevent` - End spam event",
        inline=False
    )
    
    embed.add_field(
        name="🎟️ Admin",
        value=(
            "`/ticket` - Create ticket panel\n"
            "`/giveaway` - Start giveaway\n"
            "`!embed <color> <text>` - Custom embed"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    try:
        await member.ban(reason=reason)
        embed = discord.Embed(
            description=f"✅ {member.mention} has been banned.\nReason: {reason}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to ban members!")
    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.command(name='unban')
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user_info: str):
    try:
        if user_info.startswith('<@') and user_info.endswith('>'):
            user_id = int(user_info.strip('<@!>'))
        else:
            user_id = int(user_info)
        
        await ctx.guild.unban(discord.Object(id=user_id))
        embed = discord.Embed(
            description=f"✅ User with ID {user_id} has been unbanned.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    except ValueError:
        await ctx.send("Please provide a valid user ID or mention!")
    except discord.NotFound:
        await ctx.send("This user is not banned!")
    except discord.Forbidden:
        await ctx.send("I don't have permission to unban members!")
    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.command(name='mute')
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, duration: int = 10, *, reason: str = "No reason provided"):
    try:
        await member.timeout(timedelta(minutes=duration), reason=reason)
        embed = discord.Embed(
            description=f"🔇 {member.mention} has been muted for {duration} minutes.\nReason: {reason}",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to timeout members!")
    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.command(name='unmute')
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    try:
        await member.timeout(None)
        embed = discord.Embed(
            description=f"🔊 {member.mention} has been unmuted.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to remove timeouts!")
    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.command(name='lock')
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    try:
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        embed = discord.Embed(
            description="🔒 Channel has been locked.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to manage this channel!")

@bot.command(name='unlock')
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    try:
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
        embed = discord.Embed(
            description="🔓 Channel has been unlocked.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to manage this channel!")

@bot.command(name='warn')
@commands.has_permissions(moderate_members=True)
async def warn(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)
    
    if guild_id not in warnings_data:
        warnings_data[guild_id] = {}
    
    if user_id not in warnings_data[guild_id]:
        warnings_data[guild_id][user_id] = []
    
    warning = {
        "reason": reason,
        "moderator": str(ctx.author.id),
        "timestamp": datetime.now().isoformat()
    }
    
    warnings_data[guild_id][user_id].append(warning)
    save_warnings()
    
    warn_count = len(warnings_data[guild_id][user_id])
    
    embed = discord.Embed(
        title="⚠️ Warning Issued",
        description=f"{member.mention} has been warned.\nReason: {reason}\nTotal warnings: {warn_count}",
        color=discord.Color.yellow()
    )
    await ctx.send(embed=embed)

class RemoveWarnModal(Modal, title="Remove Warning"):
    warning_number = TextInput(
        label="Warning Number",
        placeholder="Enter the warning number to remove",
        required=True,
        max_length=10
    )
    
    def __init__(self, user_id: str, guild_id: str):
        super().__init__()
        self.user_id = user_id
        self.guild_id = guild_id
    
    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("You don't have permission to remove warnings!", ephemeral=True)
            return
        
        try:
            warn_num = int(self.warning_number.value)
            
            if self.guild_id in warnings_data and self.user_id in warnings_data[self.guild_id]:
                if 1 <= warn_num <= len(warnings_data[self.guild_id][self.user_id]):
                    warnings_data[self.guild_id][self.user_id].pop(warn_num - 1)
                    save_warnings()
                    await interaction.response.send_message(f"✅ Warning #{warn_num} has been removed.", ephemeral=True)
                else:
                    await interaction.response.send_message("Invalid warning number!", ephemeral=True)
            else:
                await interaction.response.send_message("No warnings found for this user!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Please enter a valid number!", ephemeral=True)

class RemoveWarnButton(Button):
    def __init__(self, user_id: str, guild_id: str):
        super().__init__(label="Remove Warn", style=discord.ButtonStyle.red)
        self.user_id = user_id
        self.guild_id = guild_id
    
    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("You don't have permission to remove warnings!", ephemeral=True)
            return
        
        modal = RemoveWarnModal(user_id=self.user_id, guild_id=self.guild_id)
        await interaction.response.send_modal(modal)

@bot.command(name='warnings')
@commands.has_permissions(moderate_members=True)
async def warnings_command(ctx, member: discord.Member):
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)
    
    if guild_id not in warnings_data or user_id not in warnings_data[guild_id]:
        await ctx.send(f"{member.mention} has no warnings.")
        return
    
    warns = warnings_data[guild_id][user_id]
    
    if not warns:
        await ctx.send(f"{member.mention} has no warnings.")
        return
    
    embed = discord.Embed(
        title=f"⚠️ Warnings for {member.display_name}",
        color=discord.Color.orange()
    )
    
    for i, warn in enumerate(warns, 1):
        moderator = ctx.guild.get_member(int(warn['moderator']))
        mod_name = moderator.display_name if moderator else "Unknown"
        timestamp = warn['timestamp'].split('T')[0]
        
        embed.add_field(
            name=f"Warning {i}",
            value=f"**Reason:** {warn['reason']}\n**By:** {mod_name}\n**Date:** {timestamp}",
            inline=False
        )
    
    view = View()
    view.add_item(RemoveWarnButton(user_id=user_id, guild_id=guild_id))
    
    await ctx.send(embed=embed, view=view)

@bot.command(name='spamevent')
@commands.has_permissions(manage_channels=True)
async def spamevent(ctx):
    try:
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
        embed = discord.Embed(
            description="Spam event started! Start spamming!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to manage this channel!")
    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.command(name='stopspamevent')
@commands.has_permissions(manage_channels=True)
async def stopspamevent(ctx):
    try:
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        
        winner = None
        async for message in ctx.channel.history(limit=100):
            if message.author != ctx.author and not message.author.bot:
                winner = message.author
                break
        
        if winner:
            embed = discord.Embed(
                description=f"{winner.mention} has won! Congrats!",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("No messages found to determine a winner!")
            
    except discord.Forbidden:
        await ctx.send("I don't have permission to manage this channel!")
    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.command(name='embed')
@commands.has_permissions(manage_messages=True)
async def embed_command(ctx, color: str, *, message: str):
    try:
        color_map = {
            'red': discord.Color.red(),
            'blue': discord.Color.blue(),
            'green': discord.Color.green(),
            'yellow': discord.Color.gold(),
            'purple': discord.Color.purple(),
            'orange': discord.Color.orange(),
            'pink': discord.Color.pink(),
            'black': discord.Color.from_rgb(0, 0, 0),
            'white': discord.Color.from_rgb(255, 255, 255)
        }
        
        embed_color = color_map.get(color.lower(), discord.Color.blue())
        
        embed = discord.Embed(
            description=message,
            color=embed_color
        )
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.command(name='daily')
async def daily(ctx):
    guild_id = str(ctx.guild.id)
    user_id = str(ctx.author.id)
    
    if guild_id not in economy_data:
        economy_data[guild_id] = {}
    if user_id not in economy_data[guild_id]:
        economy_data[guild_id][user_id] = {'balance': 0, 'last_daily': None}
    
    user_data = economy_data[guild_id][user_id]
    now = datetime.utcnow()
    
    if user_data['last_daily']:
        last_daily = datetime.fromisoformat(user_data['last_daily'])
        time_since = (now - last_daily).total_seconds()
        if time_since < 86400:
            hours_left = int((86400 - time_since) / 3600)
            minutes_left = int(((86400 - time_since) % 3600) / 60)
            embed = discord.Embed(
                title="❌ Daily Already Claimed",
                description=f"You can claim your daily again in **{hours_left}h {minutes_left}m**",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
    
    user_data['balance'] += DAILY_AMOUNT
    user_data['last_daily'] = now.isoformat()
    save_economy()
    
    embed = discord.Embed(
        title="✅ Daily Reward",
        description=f"You claimed your daily reward!\n\n**+{DAILY_AMOUNT}** {CURRENCY_EMOJI}\n**New balance:** {user_data['balance']} {CURRENCY_EMOJI}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='balance', aliases=['bal'])
async def balance(ctx, member: discord.Member = None):
    target = member or ctx.author
    balance = get_balance(ctx.guild.id, target.id)
    
    embed = discord.Embed(
        title=f"💰 {target.display_name}'s Balance",
        description=f"**{balance}** {CURRENCY_EMOJI}",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='leaderboard', aliases=['lb'])
async def leaderboard(ctx):
    guild_id = str(ctx.guild.id)
    if guild_id not in economy_data or not economy_data[guild_id]:
        await ctx.send("No economy data yet!")
        return
    
    sorted_users = sorted(economy_data[guild_id].items(), key=lambda x: x[1]['balance'], reverse=True)[:10]
    
    embed = discord.Embed(
        title=f"🏆 Top 10 Richest Users",
        color=discord.Color.gold()
    )
    
    for i, (user_id, data) in enumerate(sorted_users, 1):
        member = ctx.guild.get_member(int(user_id))
        if member:
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"`{i}.`"
            embed.add_field(
                name=f"{medal} {member.display_name}",
                value=f"{data['balance']} {CURRENCY_EMOJI}",
                inline=False
            )
    
    await ctx.send(embed=embed)

@bot.command(name='coinflip', aliases=['cf'])
async def coinflip(ctx, bet: int, choice: str):
    if bet <= 0:
        await ctx.send("Bet must be positive!")
        return
    
    balance = get_balance(ctx.guild.id, ctx.author.id)
    if balance < bet:
        embed = discord.Embed(
            title="❌ Insufficient Funds",
            description=f"You only have **{balance}** {CURRENCY_EMOJI}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    choice = choice.lower()
    if choice not in ['heads', 'tails', 'h', 't']:
        await ctx.send("Choose either heads/h or tails/t!")
        return
    
    choice = 'heads' if choice in ['heads', 'h'] else 'tails'
    result = random.choice(['heads', 'tails'])
    won = choice == result
    
    if won:
        new_balance = add_balance(ctx.guild.id, ctx.author.id, bet)
        embed = discord.Embed(
            title="🎉 You Won!",
            description=f"The coin landed on **{result}**!\n\n**+{bet}** {CURRENCY_EMOJI}\n**New balance:** {new_balance} {CURRENCY_EMOJI}",
            color=discord.Color.green()
        )
    else:
        new_balance = remove_balance(ctx.guild.id, ctx.author.id, bet)
        embed = discord.Embed(
            title="💔 You Lost!",
            description=f"The coin landed on **{result}**!\n\n**-{bet}** {CURRENCY_EMOJI}\n**New balance:** {new_balance} {CURRENCY_EMOJI}",
            color=discord.Color.red()
        )
    
    await ctx.send(embed=embed)

@bot.command(name='dice')
async def dice_gamble(ctx, bet: int):
    if bet <= 0:
        await ctx.send("Bet must be positive!")
        return
    
    balance = get_balance(ctx.guild.id, ctx.author.id)
    if balance < bet:
        embed = discord.Embed(
            title="❌ Insufficient Funds",
            description=f"You only have **{balance}** {CURRENCY_EMOJI}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    your_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)
    
    if your_roll > bot_roll:
        winnings = bet
        new_balance = add_balance(ctx.guild.id, ctx.author.id, winnings)
        embed = discord.Embed(
            title="🎲 Dice Game - You Won!",
            description=f"Your roll: **{your_roll}**\nBot's roll: **{bot_roll}**\n\n**+{winnings}** {CURRENCY_EMOJI}\n**New balance:** {new_balance} {CURRENCY_EMOJI}",
            color=discord.Color.green()
        )
    elif your_roll < bot_roll:
        new_balance = remove_balance(ctx.guild.id, ctx.author.id, bet)
        embed = discord.Embed(
            title="🎲 Dice Game - You Lost!",
            description=f"Your roll: **{your_roll}**\nBot's roll: **{bot_roll}**\n\n**-{bet}** {CURRENCY_EMOJI}\n**New balance:** {new_balance} {CURRENCY_EMOJI}",
            color=discord.Color.red()
        )
    else:
        embed = discord.Embed(
            title="🎲 Dice Game - Tie!",
            description=f"Your roll: **{your_roll}**\nBot's roll: **{bot_roll}**\n\nNo change!",
            color=discord.Color.blue()
        )
        new_balance = balance
    
    await ctx.send(embed=embed)

@bot.command(name='slots')
async def slots(ctx, bet: int):
    if bet <= 0:
        await ctx.send("Bet must be positive!")
        return
    
    balance = get_balance(ctx.guild.id, ctx.author.id)
    if balance < bet:
        embed = discord.Embed(
            title="❌ Insufficient Funds",
            description=f"You only have **{balance}** {CURRENCY_EMOJI}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    symbols = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣']
    result = [random.choice(symbols) for _ in range(3)]
    
    if result[0] == result[1] == result[2]:
        if result[0] == '💎':
            multiplier = 10
        elif result[0] == '7️⃣':
            multiplier = 5
        else:
            multiplier = 3
        winnings = bet * multiplier
        new_balance = add_balance(ctx.guild.id, ctx.author.id, winnings)
        embed = discord.Embed(
            title="🎰 JACKPOT!",
            description=f"{result[0]} {result[1]} {result[2]}\n\n**+{winnings}** {CURRENCY_EMOJI}\n**New balance:** {new_balance} {CURRENCY_EMOJI}",
            color=discord.Color.gold()
        )
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        winnings = int(bet * 0.5)
        new_balance = add_balance(ctx.guild.id, ctx.author.id, winnings)
        embed = discord.Embed(
            title="🎰 Small Win!",
            description=f"{result[0]} {result[1]} {result[2]}\n\n**+{winnings}** {CURRENCY_EMOJI}\n**New balance:** {new_balance} {CURRENCY_EMOJI}",
            color=discord.Color.green()
        )
    else:
        new_balance = remove_balance(ctx.guild.id, ctx.author.id, bet)
        embed = discord.Embed(
            title="🎰 You Lost!",
            description=f"{result[0]} {result[1]} {result[2]}\n\n**-{bet}** {CURRENCY_EMOJI}\n**New balance:** {new_balance} {CURRENCY_EMOJI}",
            color=discord.Color.red()
        )
    
    await ctx.send(embed=embed)

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x: int, y: int, player1, player2, is_ai=False):
        super().__init__(style=discord.ButtonStyle.secondary, label='\u200b', row=y)
        self.x = x
        self.y = y
        self.player1 = player1
        self.player2 = player2
        self.is_ai = is_ai
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        
        if interaction.user != view.current_player:
            await interaction.response.send_message("Not your turn!", ephemeral=True)
            return
        
        if view.board[self.y][self.x] != 0:
            await interaction.response.send_message("Spot taken!", ephemeral=True)
            return
        
        view.board[self.y][self.x] = view.current_mark
        self.label = 'X' if view.current_mark == 1 else 'O'
        self.style = discord.ButtonStyle.primary if view.current_mark == 1 else discord.ButtonStyle.danger
        self.disabled = True
        
        winner = view.check_winner()
        if winner:
            for child in view.children:
                child.disabled = True
            
            if winner == 3:
                await interaction.response.edit_message(content="It's a tie!", view=view)
            else:
                winner_user = self.player1 if winner == 1 else self.player2
                await interaction.response.edit_message(
                    content=f"{winner_user.mention if not self.is_ai or winner == 1 else 'Bot'} wins!",
                    view=view
                )
            view.stop()
            return
        
        view.current_mark = 2 if view.current_mark == 1 else 1
        view.current_player = self.player2 if view.current_player == self.player1 else self.player1
        
        if self.is_ai and view.current_player == self.player2:
            await interaction.response.edit_message(content="Bot is thinking...", view=view)
            await asyncio.sleep(1)
            await view.ai_move(interaction)
        else:
            await interaction.response.edit_message(
                content=f"{view.current_player.mention}'s turn ({'X' if view.current_mark == 1 else 'O'})",
                view=view
            )

class TicTacToeView(discord.ui.View):
    def __init__(self, player1, player2=None):
        super().__init__(timeout=180)
        self.player1 = player1
        self.player2 = player2
        self.is_ai = player2 is None
        self.current_player = player1
        self.current_mark = 1
        self.board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        
        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y, player1, player2, self.is_ai))
    
    def check_winner(self):
        for row in self.board:
            if row[0] == row[1] == row[2] != 0:
                return row[0]
        
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] != 0:
                return self.board[0][col]
        
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != 0:
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != 0:
            return self.board[0][2]
        
        if all(self.board[y][x] != 0 for y in range(3) for x in range(3)):
            return 3
        
        return None
    
    async def ai_move(self, interaction):
        available = [(x, y) for y in range(3) for x in range(3) if self.board[y][x] == 0]
        if not available:
            return
        
        x, y = random.choice(available)
        self.board[y][x] = 2
        
        for child in self.children:
            if isinstance(child, TicTacToeButton) and child.x == x and child.y == y:
                child.label = 'O'
                child.style = discord.ButtonStyle.danger
                child.disabled = True
                break
        
        winner = self.check_winner()
        if winner:
            for child in self.children:
                child.disabled = True
            
            if winner == 3:
                await interaction.edit_original_response(content="It's a tie!", view=self)
            else:
                winner_text = self.player1.mention if winner == 1 else "Bot"
                await interaction.edit_original_response(content=f"{winner_text} wins!", view=self)
            self.stop()
            return
        
        self.current_mark = 1
        self.current_player = self.player1
        await interaction.edit_original_response(
            content=f"{self.player1.mention}'s turn (X)",
            view=self
        )

@bot.command(name='ttt')
async def tictactoe(ctx, opponent: discord.Member = None):
    if opponent == ctx.author:
        await ctx.send("You can't play against yourself!")
        return
    
    if opponent and opponent.bot:
        await ctx.send("You can't play against a bot!")
        return
    
    view = TicTacToeView(ctx.author, opponent)
    
    if opponent:
        content = f"{ctx.author.mention} vs {opponent.mention}\n{ctx.author.mention}'s turn (X)"
    else:
        content = f"{ctx.author.mention} vs Bot\n{ctx.author.mention}'s turn (X)"
    
    await ctx.send(content=content, view=view)

class RPSButton(discord.ui.Button):
    def __init__(self, choice, player1, player2=None):
        emoji_map = {'rock': '🪨', 'paper': '📄', 'scissors': '✂️'}
        super().__init__(emoji=emoji_map[choice], style=discord.ButtonStyle.primary)
        self.choice = choice
        self.player1 = player1
        self.player2 = player2
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.player1 and interaction.user != self.player2:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        
        view = self.view
        
        if view.is_ai:
            player_choice = self.choice
            bot_choice = random.choice(['rock', 'paper', 'scissors'])
            
            result = view.determine_winner(player_choice, bot_choice)
            
            for child in view.children:
                child.disabled = True
            
            emoji_map = {'rock': '🪨', 'paper': '📄', 'scissors': '✂️'}
            await interaction.response.edit_message(
                content=f"You: {emoji_map[player_choice]} | Bot: {emoji_map[bot_choice]}\n{result}",
                view=view
            )
        else:
            if not hasattr(view, 'choices'):
                view.choices = {}
            
            view.choices[interaction.user.id] = self.choice
            
            if len(view.choices) == 1:
                await interaction.response.send_message("Choice recorded! Waiting for opponent...", ephemeral=True)
            else:
                p1_choice = view.choices[self.player1.id]
                p2_choice = view.choices[self.player2.id]
                
                result = view.determine_winner(p1_choice, p2_choice, self.player1, self.player2)
                
                for child in view.children:
                    child.disabled = True
                
                emoji_map = {'rock': '🪨', 'paper': '📄', 'scissors': '✂️'}
                await interaction.response.edit_message(
                    content=f"{self.player1.mention}: {emoji_map[p1_choice]} | {self.player2.mention}: {emoji_map[p2_choice]}\n{result}",
                    view=view
                )

class RPSView(discord.ui.View):
    def __init__(self, player1, player2=None):
        super().__init__(timeout=60)
        self.player1 = player1
        self.player2 = player2
        self.is_ai = player2 is None
        
        for choice in ['rock', 'paper', 'scissors']:
            self.add_item(RPSButton(choice, player1, player2))
    
    def determine_winner(self, choice1, choice2, p1=None, p2=None):
        if choice1 == choice2:
            return "It's a tie! 🤝"
        
        wins = {
            ('rock', 'scissors'): True,
            ('paper', 'rock'): True,
            ('scissors', 'paper'): True
        }
        
        if self.is_ai:
            if wins.get((choice1, choice2)):
                return "You win! 🎉"
            else:
                return "Bot wins! 🤖"
        else:
            if wins.get((choice1, choice2)):
                return f"{p1.mention} wins! 🎉"
            else:
                return f"{p2.mention} wins! 🎉"

@bot.command(name='rps')
async def rockpaperscissors(ctx, opponent: discord.Member = None):
    if opponent == ctx.author:
        await ctx.send("You can't play against yourself!")
        return
    
    if opponent and opponent.bot:
        await ctx.send("You can't play against a bot!")
        return
    
    view = RPSView(ctx.author, opponent)
    
    if opponent:
        content = f"{ctx.author.mention} vs {opponent.mention}\nChoose your move!"
    else:
        content = f"{ctx.author.mention} vs Bot\nChoose your move!"
    
    await ctx.send(content=content, view=view)

@bot.command(name='hangman')
async def hangman(ctx):
    word = random.choice(HANGMAN_WORDS).upper()
    guessed = set()
    wrong_guesses = 0
    max_wrong = 6
    
    hangman_stages = [
        """
        ┌─────┐
        │     
        │     
        │     
        │     
        │     
        └─────
        """,
        """
        ┌─────┐
        │     O
        │     
        │     
        │     
        │     
        └─────
        """,
        """
        ┌─────┐
        │     O
        │     |
        │     
        │     
        │     
        └─────
        """,
        """
        ┌─────┐
        │     O
        │    /|
        │     
        │     
        │     
        └─────
        """,
        """
        ┌─────┐
        │     O
        │    /|\\
        │     
        │     
        │     
        └─────
        """,
        """
        ┌─────┐
        │     O
        │    /|\\
        │    /
        │     
        │     
        └─────
        """,
        """
        ┌─────┐
        │     O
        │    /|\\
        │    / \\
        │     
        │  GAME OVER
        └─────
        """
    ]
    
    def get_display():
        return ' '.join(letter if letter in guessed else '_' for letter in word)
    
    def create_embed():
        embed = discord.Embed(
            title="🎮 Hangman Game",
            color=discord.Color.blue() if wrong_guesses < max_wrong else discord.Color.red()
        )
        embed.add_field(name="Hangman", value=f"```{hangman_stages[wrong_guesses]}```", inline=False)
        embed.add_field(name="Word", value=f"```{get_display()}```", inline=False)
        embed.add_field(name="Wrong Guesses", value=f"{wrong_guesses}/{max_wrong}", inline=True)
        embed.add_field(name="Guessed Letters", value=', '.join(sorted(guessed)) if guessed else 'None', inline=True)
        embed.set_footer(text="Type a letter to guess! (60 seconds per guess)")
        return embed
    
    msg = await ctx.send(embed=create_embed())
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and len(m.content) == 1 and m.content.isalpha()
    
    while wrong_guesses < max_wrong:
        try:
            user_msg = await bot.wait_for('message', timeout=60.0, check=check)
            letter = user_msg.content.upper()
            
            try:
                await user_msg.delete()
            except:
                pass
            
            if letter in guessed:
                continue
            
            guessed.add(letter)
            
            if letter not in word:
                wrong_guesses += 1
            
            if all(l in guessed for l in word):
                win_embed = discord.Embed(
                    title="🎉 You Won!",
                    description=f"The word was: **{word}**",
                    color=discord.Color.green()
                )
                win_embed.add_field(name="Word", value=f"```{word}```", inline=False)
                win_embed.add_field(name="Wrong Guesses", value=f"{wrong_guesses}/{max_wrong}", inline=False)
                await msg.edit(embed=win_embed)
                return
            elif wrong_guesses >= max_wrong:
                lose_embed = discord.Embed(
                    title="💀 Game Over!",
                    description=f"The word was: **{word}**",
                    color=discord.Color.red()
                )
                lose_embed.add_field(name="Hangman", value=f"```{hangman_stages[max_wrong]}```", inline=False)
                await msg.edit(embed=lose_embed)
                return
            else:
                await msg.edit(embed=create_embed())
        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="⏰ Time's Up!",
                description=f"The word was: **{word}**",
                color=discord.Color.orange()
            )
            await ctx.send(embed=timeout_embed)
            return

@bot.command(name='trivia')
async def trivia(ctx):
    question = random.choice(TRIVIA_QUESTIONS)
    
    embed = discord.Embed(
        title="🧠 Trivia Challenge",
        description=question['q'],
        color=discord.Color.gold()
    )
    embed.set_footer(text="You have 45 seconds to answer!")
    
    await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    try:
        msg = await bot.wait_for('message', timeout=45.0, check=check)
        
        if msg.content.lower().strip() == question['a'].lower():
            result_embed = discord.Embed(
                title="✅ Correct!",
                description=f"{ctx.author.mention} got it right!\nThe answer is **{question['a']}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=result_embed)
        else:
            result_embed = discord.Embed(
                title="❌ Wrong!",
                description=f"The correct answer was **{question['a']}**",
                color=discord.Color.red()
            )
            await ctx.send(embed=result_embed)
    except asyncio.TimeoutError:
        timeout_embed = discord.Embed(
            title="⏰ Time's Up!",
            description=f"The answer was **{question['a']}**",
            color=discord.Color.orange()
        )
        await ctx.send(embed=timeout_embed)

@bot.command(name='math')
async def math_game(ctx):
    num1 = random.randint(1, 50)
    num2 = random.randint(1, 50)
    operation = random.choice(['+', '-', '*'])
    
    if operation == '+':
        answer = num1 + num2
        question = f"{num1} + {num2}"
    elif operation == '-':
        answer = num1 - num2
        question = f"{num1} - {num2}"
    else:
        answer = num1 * num2
        question = f"{num1} × {num2}"
    
    embed = discord.Embed(
        title="🔢 Math Challenge",
        description=f"What is **{question}**?",
        color=discord.Color.green()
    )
    embed.set_footer(text="20 seconds to answer!")
    
    await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    try:
        msg = await bot.wait_for('message', timeout=20.0, check=check)
        
        try:
            user_answer = int(msg.content.strip())
            if user_answer == answer:
                await ctx.send(f"✅ {ctx.author.mention} Correct! {question} = **{answer}**!")
            else:
                await ctx.send(f"❌ Wrong! {question} = **{answer}**")
        except ValueError:
            await ctx.send(f"❌ Invalid number! The answer was **{answer}**")
    except asyncio.TimeoutError:
        await ctx.send(f"⏰ Time's up! {question} = **{answer}**")

@bot.command(name='wordguess')
async def wordguess(ctx):
    words = ['PYTHON', 'DISCORD', 'COMPUTER', 'KEYBOARD', 'MUSIC', 'GUITAR']
    word = random.choice(words)
    scrambled = ''.join(random.sample(word, len(word)))
    
    while scrambled == word and len(word) > 2:
        scrambled = ''.join(random.sample(word, len(word)))
    
    embed = discord.Embed(
        title="🔤 Word Scramble",
        description=f"Unscramble: **{scrambled}**",
        color=discord.Color.purple()
    )
    embed.add_field(name="Hint", value=f"{len(word)} letters")
    embed.set_footer(text="30 seconds to guess!")
    
    await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    try:
        msg = await bot.wait_for('message', timeout=30.0, check=check)
        
        if msg.content.upper().strip() == word:
            await ctx.send(f"✅ {ctx.author.mention} Correct! The word was **{word}**!")
        else:
            await ctx.send(f"❌ Wrong! The word was **{word}**")
    except asyncio.TimeoutError:
        await ctx.send(f"⏰ Time's up! The word was **{word}**")

@bot.command(name='8ball')
async def eightball(ctx, *, question: str = None):
    if not question:
        await ctx.send("❌ Ask a question! Example: `!8ball Will I win?`")
        return
    
    responses = [
        "It is certain! ✅", "Without a doubt! 💯", "Yes, definitely! 👍",
        "Most likely! 📊", "Outlook good! 🌟", "Yes! ✨",
        "Reply hazy, try again! 🌫️", "Ask again later! ⏰",
        "Cannot predict now! 🔮", "Don't count on it! ❌",
        "My reply is no! 🚫", "Very doubtful! 🤔"
    ]
    response = random.choice(responses)
    
    embed = discord.Embed(
        title="🔮 Magic 8-Ball",
        description=f"**Question:** {question}\n\n**Answer:** {response}",
        color=discord.Color.purple()
    )
    embed.set_footer(text=f"Asked by {ctx.author.name}")
    
    await ctx.send(embed=embed)

@bot.command(name='wyr')
async def wouldyourather(ctx):
    questions = [
        "Would you rather have the ability to fly or be invisible?",
        "Would you rather be able to talk to animals or speak all languages?",
        "Would you rather live in the past or the future?",
        "Would you rather have unlimited money or unlimited time?",
        "Would you rather explore space or the deep ocean?",
    ]
    question = random.choice(questions)
    
    embed = discord.Embed(
        title="🤔 Would You Rather?",
        description=question,
        color=discord.Color.blue()
    )
    embed.set_footer(text="React with 1️⃣ or 2️⃣!")
    
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("1️⃣")
    await msg.add_reaction("2️⃣")

@bot.command(name='guess')
async def guessnumber(ctx):
    number = random.randint(1, 100)
    attempts = 0
    max_attempts = 7
    
    embed = discord.Embed(
        title="🎯 Number Guessing Game",
        description="I'm thinking of a number between **1-100**!\nYou have **7 attempts**!",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    while attempts < max_attempts:
        try:
            msg = await bot.wait_for('message', timeout=60.0, check=check)
            attempts += 1
            
            try:
                guess = int(msg.content.strip())
                
                if guess < 1 or guess > 100:
                    await ctx.send("❌ Number between 1-100!")
                    attempts -= 1
                    continue
                
                if guess == number:
                    await ctx.send(f"🎉 {ctx.author.mention} Correct in **{attempts}** attempt(s)! Number was **{number}**!")
                    return
                elif guess < number:
                    await ctx.send(f"📈 Higher! ({max_attempts - attempts} left)")
                else:
                    await ctx.send(f"📉 Lower! ({max_attempts - attempts} left)")
                    
            except ValueError:
                await ctx.send("❌ Enter a valid number!")
                attempts -= 1
                
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ Time's up! Number was **{number}**")
            return
    
    await ctx.send(f"💀 Game Over! Number was **{number}**")

@bot.command(name='memory')
async def memory(ctx):
    emojis = ['🍎', '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '🍒']
    sequence = [random.choice(emojis) for _ in range(5)]
    
    embed = discord.Embed(
        title="🧠 Memory Game",
        description="Memorize this sequence!\n\n" + " ".join(sequence),
        color=discord.Color.blue()
    )
    embed.set_footer(text="10 seconds to memorize!")
    
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(10)
    
    embed.description = "What was the sequence? (Type emojis in order, no spaces)"
    await msg.edit(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    try:
        user_msg = await bot.wait_for('message', timeout=30.0, check=check)
        user_sequence = ''.join(user_msg.content.split())
        correct_sequence = ''.join(sequence)
        
        if user_sequence == correct_sequence:
            await ctx.send(f"🎉 {ctx.author.mention} Perfect memory!")
        else:
            await ctx.send(f"❌ Correct sequence: {' '.join(sequence)}")
    except asyncio.TimeoutError:
        await ctx.send(f"⏰ Time's up! Sequence: {' '.join(sequence)}")

@bot.command(name='typerace')
async def typerace(ctx):
    texts = [
        "The quick brown fox jumps over the lazy dog",
        "Python is an amazing programming language",
        "Discord bots are fun to create and use",
        "Practice makes perfect in everything you do"
    ]
    text = random.choice(texts)
    
    embed = discord.Embed(
        title="⌨️ Typing Speed Test",
        description=f"Type this as fast as you can:\n\n```{text}```",
        color=discord.Color.green()
    )
    embed.set_footer(text="Timer starts now!")
    
    await ctx.send(embed=embed)
    start_time = time.time()
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    try:
        msg = await bot.wait_for('message', timeout=60.0, check=check)
        end_time = time.time()
        elapsed = round(end_time - start_time, 2)
        
        if msg.content.strip() == text:
            wpm = int((len(text.split()) / elapsed) * 60)
            await ctx.send(f"✅ {ctx.author.mention} Perfect! Time: **{elapsed}s** | Speed: **{wpm} WPM** 🚀")
        else:
            accuracy = sum(1 for a, b in zip(msg.content, text) if a == b) / len(text) * 100
            await ctx.send(f"⚠️ Time: **{elapsed}s** | Accuracy: **{accuracy:.1f}%**")
    except asyncio.TimeoutError:
        await ctx.send("⏰ Time's up!")

ticket_counters = {}

class TicketButton(discord.ui.Button):
    def __init__(self, label, emoji, allowed_roles):
        super().__init__(
            label=label if label else None,
            emoji=emoji if emoji else None,
            style=discord.ButtonStyle.primary
        )
        self.allowed_roles = allowed_roles
        self.button_label = label
    
    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user
        
        if guild.id not in ticket_counters:
            ticket_counters[guild.id] = 0
        
        ticket_counters[guild.id] += 1
        ticket_num = ticket_counters[guild.id]
        
        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category("Tickets")
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        for role in self.allowed_roles:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        channel = await guild.create_text_channel(
            name=f"ticket-{ticket_num}",
            category=category,
            overwrites=overwrites
        )
        
        embed = discord.Embed(
            title=f"Ticket #{ticket_num}",
            description=f"Welcome {user.mention}! Support will be with you shortly.",
            color=discord.Color.green()
        )
        embed.add_field(name="Created by", value=user.mention, inline=True)
        embed.add_field(name="Button", value=self.button_label, inline=True)
        
        close_button = CloseTicketButton()
        view = discord.ui.View(timeout=None)
        view.add_item(close_button)
        
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Ticket created! {channel.mention}", ephemeral=True)

class CloseTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Close Ticket", emoji="🔒", style=discord.ButtonStyle.danger)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class TicketPanel(discord.ui.View):
    def __init__(self, buttons_data, allowed_roles):
        super().__init__(timeout=None)
        for btn_data in buttons_data:
            self.add_item(TicketButton(
                label=btn_data['label'],
                emoji=btn_data['emoji'],
                allowed_roles=allowed_roles
            ))

pending_tickets = {}

@bot.tree.command(name="ticket", description="Create a ticket panel")
@app_commands.describe(
    button1="First button (can include emoji)",
    channel="Channel for ticket panel",
    roles="Roles that can see tickets",
    button2="Second button (optional)",
    button3="Third button (optional)",
    button4="Fourth button (optional)",
    image="Image URL (optional)"
)
async def ticket_slash(
    interaction: discord.Interaction,
    button1: str,
    channel: discord.TextChannel,
    roles: str,
    button2: str = None,
    button3: str = None,
    button4: str = None,
    image: str = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    role_ids = [r.strip().replace('<@&', '').replace('>', '') for r in roles.split()]
    role_mentions = []
    for rid in role_ids:
        try:
            role = interaction.guild.get_role(int(rid))
            if role:
                role_mentions.append(role)
        except:
            pass
    
    if not role_mentions:
        await interaction.followup.send("❌ Provide valid roles!", ephemeral=True)
        return
    
    buttons = [button1]
    if button2:
        buttons.append(button2)
    if button3:
        buttons.append(button3)
    if button4:
        buttons.append(button4)
    
    await interaction.followup.send("What text would you like to be in the ticket panel embed?", ephemeral=True)
    
    pending_tickets[interaction.user.id] = {
        'channel': channel,
        'roles': role_mentions,
        'buttons': buttons,
        'image': image
    }
    
    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel
    
    try:
        msg = await bot.wait_for('message', timeout=120.0, check=check)
        embed_text = msg.content
        
        try:
            await msg.delete()
        except:
            pass
        
        embed = discord.Embed(
            title="🎫 Support Tickets",
            description=embed_text,
            color=discord.Color.blue()
        )
        
        if image:
            embed.set_image(url=image)
        
        buttons_data = []
        for btn in buttons:
            emoji_obj = None
            label = btn
            
            if '<' in btn and '>' in btn:
                try:
                    emoji_part = btn[btn.find('<'):btn.find('>')+1]
                    try:
                        emoji_obj = discord.PartialEmoji.from_str(emoji_part)
                    except:
                        pass
                    label = btn.replace(emoji_part, '').strip()
                except:
                    pass
            
            buttons_data.append({
                'label': label if label else btn,
                'emoji': emoji_obj
            })
        
        view = TicketPanel(buttons_data, role_mentions)
        await channel.send(embed=embed, view=view)
        
        await interaction.followup.send(f"✅ Ticket panel created in {channel.mention}!", ephemeral=True)
        
        if interaction.user.id in pending_tickets:
            del pending_tickets[interaction.user.id]
            
    except asyncio.TimeoutError:
        await interaction.followup.send("❌ Timeout! Try again.", ephemeral=True)
        if interaction.user.id in pending_tickets:
            del pending_tickets[interaction.user.id]

active_giveaways = {}

class GiveawayButton(discord.ui.Button):
    def __init__(self, giveaway_id):
        super().__init__(
            label="Join",
            emoji="🎉",
            style=discord.ButtonStyle.green,
            custom_id=f"giveaway_{giveaway_id}"
        )
        self.giveaway_id = giveaway_id
    
    async def callback(self, interaction: discord.Interaction):
        if self.giveaway_id not in active_giveaways:
            await interaction.response.send_message("❌ This giveaway has ended!", ephemeral=True)
            return
        
        giveaway_data = active_giveaways[self.giveaway_id]
        participants = giveaway_data['participants']
        
        if interaction.user.id in participants:
            await interaction.response.send_message("❌ You've already joined this giveaway!", ephemeral=True)
            return
        
        participants.add(interaction.user.id)
        
        embed = interaction.message.embeds[0]
        for i, field in enumerate(embed.fields):
            if "🎉 Join" in field.name:
                embed.set_field_at(i, name=field.name, value=f"{len(participants)}/∞", inline=field.inline)
                break
        
        await interaction.response.edit_message(embed=embed)
        await interaction.followup.send("✅ You've entered the giveaway! Good luck! 🍀", ephemeral=True)

class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.add_item(GiveawayButton(giveaway_id))

@bot.tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(
    title="Giveaway title",
    prize="What are you giving away?",
    time="Duration (e.g., 10m, 2h, 1d)",
    winners="Number of winners",
    channel="Channel to post (optional)"
)
async def giveaway_slash(
    interaction: discord.Interaction,
    title: str,
    prize: str,
    time: str,
    winners: int = 1,
    channel: discord.TextChannel = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only!", ephemeral=True)
        return
    
    if winners < 1:
        await interaction.response.send_message("❌ Winners must be at least 1!", ephemeral=True)
        return
    
    import re
    time_match = re.match(r'(\d+)([mhd])', time.lower())
    if not time_match:
        await interaction.response.send_message("❌ Invalid time format! Use format like: 10m, 2h, 1d", ephemeral=True)
        return
    
    amount, unit = int(time_match.group(1)), time_match.group(2)
    
    if unit == 'm':
        duration_seconds = amount * 60
        duration_text = f"{amount} minute{'s' if amount != 1 else ''}"
    elif unit == 'h':
        duration_seconds = amount * 3600
        duration_text = f"{amount} hour{'s' if amount != 1 else ''}"
    elif unit == 'd':
        duration_seconds = amount * 86400
        duration_text = f"{amount} day{'s' if amount != 1 else ''}"
    
    target_channel = channel or interaction.channel
    
    end_time = datetime.utcnow() + timedelta(seconds=duration_seconds)
    timestamp = int(end_time.timestamp())
    
    giveaway_id = f"{interaction.guild.id}_{int(datetime.utcnow().timestamp())}"
    
    embed = discord.Embed(
        title=title,
        color=discord.Color.gold()
    )
    embed.add_field(name="🎁 Prize:", value=prize, inline=False)
    embed.add_field(name="👥 Winners:", value=str(winners), inline=False)
    embed.add_field(name="⏱️ Time:", value=f"Ends <t:{timestamp}:R> (<t:{timestamp}:F>)", inline=False)
    embed.add_field(name="🎉 Join", value="0/∞", inline=False)
    embed.set_footer(text="Good luck!")
    
    view = GiveawayView(giveaway_id)
    
    await interaction.response.send_message(f"✅ Giveaway started in {target_channel.mention}!", ephemeral=True)
    
    giveaway_msg = await target_channel.send(embed=embed, view=view)
    
    active_giveaways[giveaway_id] = {
        'message': giveaway_msg,
        'participants': set(),
        'prize': prize,
        'title': title,
        'winners': winners,
        'host': interaction.user,
        'channel': target_channel
    }
    
    await asyncio.sleep(duration_seconds)
    
    if giveaway_id not in active_giveaways:
        return
    
    giveaway_data = active_giveaways[giveaway_id]
    participants_ids = list(giveaway_data['participants'])
    
    if len(participants_ids) == 0:
        await target_channel.send("❌ No participants entered the giveaway!")
        del active_giveaways[giveaway_id]
        return
    
    guild = interaction.guild
    participants = []
    for user_id in participants_ids:
        user = guild.get_member(user_id)
        if user:
            participants.append(user)
    
    if len(participants) == 0:
        await target_channel.send("❌ No valid participants!")
        del active_giveaways[giveaway_id]
        return
    
    actual_winners = min(winners, len(participants))
    winners_list = random.sample(participants, actual_winners)
    
    winner_mentions = ' '.join([winner.mention for winner in winners_list])
    
    result_embed = discord.Embed(
        title=title,
        description=f"The winner{'s' if len(winners_list) > 1 else ''} of this giveaway {'are' if len(winners_list) > 1 else 'is'} tagged above! Congratulations 🎉",
        color=discord.Color.green()
    )
    result_embed.add_field(name="🎁 Prize:", value=prize, inline=False)
    result_embed.add_field(name="Participants:", value=str(len(participants)), inline=False)
    
    await target_channel.send(winner_mentions, embed=result_embed)
    
    try:
        disabled_view = GiveawayView(giveaway_id)
        for item in disabled_view.children:
            item.disabled = True
        
        embed = giveaway_msg.embeds[0]
        await giveaway_msg.edit(embed=embed, view=disabled_view)
    except:
        pass
    
    del active_giveaways[giveaway_id]

if __name__ == '__main__':
    token = os.getenv('DISCORD_BOT_TOKEN')
    
    if not token:
        print('Error: DISCORD_BOT_TOKEN not set')
        print('Add your Discord bot token to Secrets')
    else:
        try:
            bot.run(token)
        except Exception as e:
            print(f'Error: {e}')
            