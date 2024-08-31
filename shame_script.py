import configparser
import os
from datetime import datetime, time
from typing import List, Union


import discord
import requests
from discord.ext import commands, tasks
from discord_signup import signup
from table2ascii import table2ascii, TableStyle, Alignment

# Read the settings.cfg file
config_path = os.path.join(os.path.dirname(__file__), "settings.cfg")
config = configparser.ConfigParser()
config.read(config_path)

# Load the Discord bot token and channel ID from the config file
DISCORD_TOKEN = config.get("DISCORD", "TOKEN")
CHANNEL_ID = config.getint("DISCORD", "CHANNEL_ID")
SERVER_ID = config.getint("DISCORD", "SERVER_ID")
LAST_ONLINE = config.get("DISCORD", "LAST_ONLINE", fallback=None)

TODOIST_API = "https://api.todoist.com/rest/v2/tasks"

SCHEDULED_UTC_POST_TIME = time(hour=2)

TASK_MAX_LENGTH = 70
INTERVAL_MAX_LENGTH = 20
TASK_TABLE_LIMIT = 10
DISCORD_MESSAGE_LIMIT = 2000


async def safe_send(channel: discord.TextChannel, message: str) -> discord.Message:
    safe_message = message
    if len(message) > DISCORD_MESSAGE_LIMIT:
        safe_message = message[:DISCORD_MESSAGE_LIMIT]
    return await channel.send(safe_message)


# Function to get all tasks with a specific label and due today or overdue
def get_tasks(api_token, label_name):
    headers = {"Authorization": f"Bearer {api_token}"}

    # Get all tasks
    params = {"filter": f"(today | overdue) & !@{label_name}"}
    response = requests.get(TODOIST_API, params=params, headers=headers)
    return response.json()


def add_label(tasks, api_token, label_name):
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    # First, we need to get the ID of the label from the label name
    labels_response = requests.get(
        "https://api.todoist.com/rest/v2/labels", headers=headers
    )
    labels = labels_response.json()
    label_id = None

    for label in labels:
        if label["name"] == label_name:
            label_id = label["id"]
            break

    if label_id is None:
        # Create the label if it does not exist
        create_label_response = requests.post(
            "https://api.todoist.com/rest/v2/labels",
            json={"name": label_name, "color": "lavender"},
            headers=headers,
        )

        if create_label_response.status_code == 200:
            label_id = create_label_response.json()["id"]
            print(f'Label "{label_name}" created successfully.')
        else:
            print(
                f'Failed to create label "{label_name}": {create_label_response.status_code} - {create_label_response.text}'
            )
            return

    for task in tasks:
        task_id = task["id"]
        labels = task.get("labels", [])
        if label_name not in labels:
            labels.append(label_name)

        data = {"labels": labels}

        # Update the task with the new label
        update_response = requests.post(
            f"{TODOIST_API}/{task_id}", json=data, headers=headers
        )

        if update_response.status_code == 200:
            print(f"Task {task_id} updated successfully.")
        else:
            print(
                f"Failed to update task {task_id}: {update_response.status_code} - {update_response.text}"
            )


def string_shorten(message: str, max_length: int):
    message = message.strip()

    if len(message) <= max_length:
        return message

    return message[: max_length - 3] + "..."


# Initialize the bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(intents=intents, command_prefix="!")


@bot.event
async def on_ready():
    print(f"Bot is ready. Logged in as {bot.user}")
    synced = await bot.tree.sync()
    fetch_and_send_tasks.start()
    for command in synced:
        print(command.name)


async def paginate_message_send(
    channel: discord.TextChannel,
    message_content: List[str],
    max_page: int = DISCORD_MESSAGE_LIMIT,
):
    page_start = 0
    page_length = 0
    for line, content in enumerate(message_content):
        if len(content) + 1 + page_length > max_page:
            # There needs to be room for the next section, and a newline
            await safe_send(channel, "\n".join(message_content[page_start:line]))
            page_start = line
            page_length = 0

        page_length += len(content) + 1  # add newline char

    print(message_content)
    await safe_send(channel, "\n".join(message_content[page_start:]))


@tasks.loop(time=SCHEDULED_UTC_POST_TIME)
async def fetch_and_send_tasks():
    label_name = "exclude"  # Replace with your desired label

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("Channel not found")
        return

    message_content = ["**Daily Task Readout**"]
    # Load keys from the config file
    todoist_key_by_email = dict(config.items("TODOIST_KEY_BY_EMAIL"))
    discord_id_by_email = dict(config.items("DISCORD_ID_BY_EMAIL"))
    for user_email, api_token in todoist_key_by_email.items():
        discord_id = int(discord_id_by_email[user_email])
        tasks: List[dict[str, Union[dict[str, str], str]]] = get_tasks(
            api_token, label_name
        )
        add_label(tasks, api_token, "shame")
        discord_user = await bot.fetch_user(discord_id)

        if tasks:
            task_count = len(tasks)
            if task_count > TASK_TABLE_LIMIT:
                # subtract 1 from the task limit to leave room for the "more tasks" line
                tasks = tasks[: TASK_TABLE_LIMIT - 1]
                tasks.append(
                    {
                        "content": f"...{task_count - (TASK_TABLE_LIMIT - 1)} more task(s)"
                    }
                )
            table = table2ascii(
                header=["Task", "Due"],
                body=[
                    [
                        string_shorten(task.get("content", ""), TASK_MAX_LENGTH),
                        string_shorten(
                            task.get("due", {}).get("string", ""), INTERVAL_MAX_LENGTH
                        ),
                    ]
                    for task in tasks
                ],
                style=TableStyle.from_string("┏━┳┳┓┃┃┃┣━╋╋┫     ┗┻┻┛  ┳┻  ┳┻"),
                alignments=Alignment.LEFT,
                # extra is added for the required padding
                column_widths=[TASK_MAX_LENGTH + 2, INTERVAL_MAX_LENGTH + 2],
            )
            message_content.append(
                f"*Tasks for {discord_user.mention}*\n```\n{table}\n```"
            )
        else:
            message_content.append(f"{discord_user.mention} Completed all tasks")

    await paginate_message_send(channel, message_content)

    today = datetime.now().strftime("%Y-%m-%d")

    thread_message = await safe_send(
        channel, "Discuss Task Completion in following Thread:"
    )

    await channel.create_thread(
        name=f"Daily Task Thread {today}",
        message=thread_message,
        reason="Daily Task Thread",
    )


@discord.app_commands.describe(user_to_signup="Mention of user")
@bot.tree.command(name="signup")
async def signup_passthrough(
    interaction: discord.Interaction, user_to_signup: discord.Member
):
    await interaction.response.defer(ephemeral=True, thinking=True)
    await signup(interaction, user_to_signup, bot)


bot.run(DISCORD_TOKEN)
