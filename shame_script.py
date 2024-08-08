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

def add_label(tasks, api_token, label_name):
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }

    # First, we need to get the ID of the label from the label name
    labels_response = requests.get('https://api.todoist.com/rest/v2/labels', headers=headers)
    labels = labels_response.json()
    label_id = None

    for label in labels:
        if label['name'] == label_name:
            label_id = label['id']
            break

    if label_id is None:
        # Create the label if it does not exist
        create_label_response = requests.post(
            'https://api.todoist.com/rest/v2/labels',
            json={'name': label_name, 'color': 'lavender'},
            headers=headers
        )

        if create_label_response.status_code == 200:
            label_id = create_label_response.json()['id']
            print(f'Label "{label_name}" created successfully.')
        else:
            print(f'Failed to create label "{label_name}": {create_label_response.status_code} - {create_label_response.text}')
            return

    for task in tasks:
        task_id = task['id']
        labels = task.get('labels', [])
        if label_name not in labels:
            labels.append(label_name)

        data = {
            'labels': labels
        }

        # Update the task with the new label
        update_response = requests.post(f'{TODOIST_API}/{task_id}', json=data, headers=headers)

        if update_response.status_code == 200:
            print(f'Task {task_id} updated successfully.')
        else:
            print(f'Failed to update task {task_id}: {update_response.status_code} - {update_response.text}')

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
        add_label(tasks, api_token, 'shame')
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
