import logging
from datetime import datetime, time
from http import HTTPStatus
from typing import List

import aiohttp
import discord
from discord.ext import commands, tasks
from table2ascii import Alignment, TableStyle, table2ascii

from discord_signup import signup
from log_setup import trace_config
from shame_command import shame
from Task import Label, Task
from utils.Config import load_config
from utils.Database import get_users

logger = logging.getLogger(__name__)
logger.info("Bot is starting up...")

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
async def get_tasks(
    api_token: str, label_name: str, session: aiohttp.ClientSession
) -> List[Task] | None:
    headers = {"Authorization": f"Bearer {api_token}"}

    # Get all tasks
    params = {"filter": f"(today | overdue) & !@{label_name}"}
    async with session.get(TODOIST_API, params=params, headers=headers) as response:
        logger.debug("Request from todoist")
        return await response.json()


async def add_label(
    task_list: List[Task],
    api_token: str,
    label_name: str,
    session: aiohttp.ClientSession,
) -> None:
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    # First, we need to get the ID of the label from the label name
    async with session.get(
        "https://api.todoist.com/rest/v2/labels", headers=headers
    ) as labels_response:
        labels: List[Label] = await labels_response.json()

    label_id = next(
        (label["id"] for label in labels if label["name"] == label_name), None
    )

    if label_id is None:
        # Create the label if it does not exist
        async with session.post(
            "https://api.todoist.com/rest/v2/labels",
            json={"name": label_name, "color": "lavender"},
            headers=headers,
        ) as create_label_response:
            if create_label_response.status == HTTPStatus.OK:
                await create_label_response.json()
                logger.info('Label "%s" created successfully.', label_name)
            else:
                logger.info(
                    'Failed to create label "%s": %d - %s',
                    label_name,
                    create_label_response.status,
                    await create_label_response.text(),
                )
                return

    for task in task_list:
        task_id = task.get("id", 0)
        task_labels = task.get("labels", [])
        if label_name in labels:
            continue

        task_labels.append(label_name)
        data = {"labels": task_labels}

        # Update the task with the new label
        async with session.post(
            f"{TODOIST_API}/{task_id}", json=data, headers=headers
        ) as update_response:
            if update_response.status == HTTPStatus.OK:
                logger.info("Task %s updated successfully.", task_id)
            else:
                logger.info(
                    "Failed to update task %s: %d - %s",
                    task_id,
                    update_response.status,
                    await update_response.text(),
                )


def string_shorten(message: str, max_length: int) -> str:
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
async def on_ready() -> None:
    logger.info("Bot is ready. Logged in as %s", bot.user)
    try:
        synced = await bot.tree.sync()
        fetch_and_send_tasks.start()
        for command in synced:
            logger.info("Command synced: %s", command.name)
    except Exception:
        logger.exception("Error during on_ready")


async def paginate_message_send(
    channel: discord.TextChannel,
    message_content: List[str],
    max_page: int = DISCORD_MESSAGE_LIMIT,
) -> None:
    page_start = 0
    page_length = 0
    for line, content in enumerate(message_content):
        if len(content) + 1 + page_length > max_page:
            await safe_send(channel, "\n".join(message_content[page_start:line]))
            page_start = line
            page_length = 0
        page_length += len(content) + 1  # add newline char

    logger.debug("Message content: %s", message_content)
    await safe_send(channel, "\n".join(message_content[page_start:]))


@tasks.loop(time=SCHEDULED_UTC_POST_TIME)
async def fetch_and_send_tasks() -> None:
    label_name = "exclude"  # Replace with your desired label

    channel: discord.TextChannel = bot.get_channel(CHANNEL_ID)  # type: ignore
    if not channel:
        logger.error("Channel not found")
        return

    logger.info("Fetching and sending tasks for channel: %d", CHANNEL_ID)

    message_content = ["**Daily Task Readout**"]

    users = get_users()

    async with aiohttp.ClientSession(trace_configs=[trace_config]) as session:
        for user in users:
            logger.info("Processing tasks for user: %s", user.email)

            task_list = await get_tasks(user.todoist_token, label_name, session)
            discord_user = await bot.fetch_user(user.discord_id)

            if not task_list:
                message_content.append(f"{discord_user.mention} Completed all tasks")
                continue

            await add_label(task_list, user.todoist_token, "shame", session)

            task_count = len(task_list)
            if task_count > TASK_TABLE_LIMIT:
                # subtract 1 from the task limit to leave room for the "more tasks" line
                task_list = task_list[: TASK_TABLE_LIMIT - 1]
                task_list.append(
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
                    for task in task_list
                ],
                style=TableStyle.from_string("┏━┳┳┓┃┃┃┣━╋╋┫     ┗┻┻┛  ┳┻  ┳┻"),
                alignments=Alignment.LEFT,
                # extra is added for the required padding
                column_widths=[TASK_MAX_LENGTH + 2, INTERVAL_MAX_LENGTH + 2],
            )
            message_content.append(
                f"*Tasks for {discord_user.mention}*\n```\n{table}\n```"
            )

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
) -> None:
    logger.info("Signup command received for user: %s", user_to_signup.name)
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        await signup(interaction, user_to_signup, bot)
        logger.info("Signup successful for user: %s", user_to_signup.name)
    except Exception:
        logger.exception("Error during signup")


@discord.app_commands.describe(user_to_shame="Mention of user")
@bot.tree.command(name="shame")
async def shame_passthrough(
    interaction: discord.Interaction, user_to_shame: discord.Member
) -> None:
    logger.info("Shame command received for user: %s", user_to_shame.name)

    await interaction.response.defer(ephemeral=False, thinking=True)
    try:
        await shame(interaction, user_to_shame)
        logger.info("Shaming successful for user: %s", user_to_shame.name)

    except Exception:
        logger.exception("Error during shaming: %s")
        await interaction.followup.send(
            "An error occurred while processing the shame command."
        )


config = load_config()
bot.run(config.discord.token, log_handler=None)
