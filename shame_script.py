import requests
import discord
from datetime import datetime
from discord.ext import commands
from table2ascii import table2ascii, PresetStyle, Alignment
import configparser

# Read the settings.cfg file
config = configparser.ConfigParser()
config.read('settings.cfg')

# Load the USER_API_TOKENS from the config file
USER_API_TOKENS = dict(config.items('USER_API_TOKENS'))

# Load the Discord bot token and channel ID from the config file
DISCORD_TOKEN = config.get('DISCORD', 'TOKEN')
CHANNEL_ID = config.getint('DISCORD', 'CHANNEL_ID')

TODOIST_API = 'https://api.todoist.com/rest/v2/tasks'


# Function to get all tasks with a specific label and due today or overdue
def get_tasks(api_token, label_name):
    headers = {
        'Authorization': f'Bearer {api_token}'
    }
    today = datetime.now().strftime('%Y-%m-%d')

    # Get all tasks
    params = {
        'filter': f'(today | overdue) & !@{label_name}'
    }
    response = requests.get(TODOIST_API, params=params, headers=headers)
    return response.json()


# Initialize the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(intents=intents, command_prefix='!')


@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user}')
    await fetch_and_send_tasks()


async def fetch_and_send_tasks():
    label_name = 'exclude'  # Replace with your desired label

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print('Channel not found')
        return

    embed = discord.Embed(title="Daily Task Check", description="Readout of task status", color=0xFF5733)
    message_content = []

    for discord_id, api_token in USER_API_TOKENS.items():
        tasks = get_tasks(api_token, label_name)
        discord_user = await bot.fetch_user(discord_id)

        if tasks:
            message_content.append(f"Tasks for {discord_user.mention}")
            table = table2ascii(
                header=["Task", "Due"],
                body=[[task['content'], task['due']['string']] for task in tasks],
                style=PresetStyle.thin_compact,
                alignments=Alignment.LEFT
            )
            message_content.append(f"```\n{table}\n```")
        else:
            message_content.append(f"{discord_user.mention} Completed all tasks")

    embed.add_field(
        name="Tasks",
        value="\n".join(message_content),
        inline=False
    )
    embed.set_footer(text="Shame all users who failed to finish their tasks")

    await channel.send(embed=embed)
    await bot.close()


# Run the bot
bot.run(DISCORD_TOKEN)
