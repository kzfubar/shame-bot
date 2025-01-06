import logging
from datetime import datetime
from typing import List

import aiohttp
import discord
from discord.ext import commands, tasks
from table2ascii import Alignment, TableStyle, table2ascii

from discord_signup import signup
from log_setup import log_setup, trace_config
from shame_command import shame
from todoist.rest import add_label, get_tasks
from todoist.types import Filter
from utils.Config import load_config
from utils.Constants import DUE_TODAY, SHAME_LABEL
from utils.Database import Score, get_session, get_users

logger = logging.getLogger(__name__)
logger.info("Bot is starting up...")

SCHEDULED_UTC_POST_TIME = datetime.strptime(
    load_config().shame_script.utc_runtime, "%H:%M"
).time()

TASK_MAX_LENGTH = 70
INTERVAL_MAX_LENGTH = 20
TASK_TABLE_LIMIT = 10
DISCORD_MESSAGE_LIMIT = 2000


async def safe_send(channel: discord.TextChannel, message: str) -> discord.Message:
    safe_message = message
    if len(message) > DISCORD_MESSAGE_LIMIT:
        safe_message = message[:DISCORD_MESSAGE_LIMIT]
    return await channel.send(safe_message)


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

    channel = bot.get_channel(load_config().discord.channel_id)
    if not channel:
        logger.error("Channel not found")
        return

    if not isinstance(channel, discord.TextChannel):
        raise TypeError("Incorrect channel type")

    logger.info("Fetching and sending tasks for channel: %d", config.discord.channel_id)

    message_content = ["**Daily Task Readout**"]

    async with aiohttp.ClientSession(trace_configs=[trace_config]) as client_session:
        with get_session() as database_session:
            users = get_users(database_session)
            for user in users:
                logger.info("Processing tasks for user: %s", user.email)

                task_list = await get_tasks(
                    client_session,
                    user.todoist_token,
                    DUE_TODAY & ~Filter(label=label_name),
                )

                if not user.discord_id:
                    continue

                discord_user = await bot.fetch_user(user.discord_id)

                if not user.score:
                    user.score = Score(streak=0)

                # All tasks completed
                if not task_list:
                    user.score.streak += 1
                    message_content.append(
                        f"{discord_user.mention} Completed all tasks | Streak: {user.score.streak}"
                    )
                    continue

                # Otherwise, proceed with shaming
                user.score.streak = 0
                await add_label(
                    client_session, user.todoist_token, task_list, SHAME_LABEL
                )

                task_table = [
                    [
                        string_shorten(task.content, TASK_MAX_LENGTH),
                        string_shorten(
                            task.due.string if task.due else "", INTERVAL_MAX_LENGTH
                        ),
                    ]
                    for task in task_list
                ]
                task_count = len(task_list)

                if task_count > TASK_TABLE_LIMIT:
                    # subtract 1 from the task limit to leave room for the "more tasks" line
                    task_table = task_table[: TASK_TABLE_LIMIT - 1]
                    task_table.append(
                        [f"{task_count - (TASK_TABLE_LIMIT - 1)} more task(s)", ""]
                    )

                table = table2ascii(
                    header=["Task", "Due"],
                    body=task_table,
                    style=TableStyle.from_string("┏━┳┳┓┃┃┃┣━╋╋┫     ┗┻┻┛  ┳┻  ┳┻"),
                    alignments=Alignment.LEFT,
                    # extra is added for the required padding
                    column_widths=[TASK_MAX_LENGTH + 2, INTERVAL_MAX_LENGTH + 2],
                )

                message_content.append(
                    f"*Tasks for {discord_user.mention} | Streak: {user.score.streak}*\n```\n{table}\n```"
                )
            database_session.commit()

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


if __name__ == "__main__":
    log_setup()
    config = load_config()
    bot.run(config.discord.token, log_handler=None)
