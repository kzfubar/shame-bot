import asyncio
import logging
import re
from typing import Callable, Optional

import discord
from discord.ext import commands

from utils.Config import load_config
from utils.Database import EmailClaimedError, add_discord_to_user, discord_id_exists

logger = logging.getLogger(__name__)

ONE_MINUTE = 60
SIGNUP_TIMEOUT = ONE_MINUTE * 10
EMAIL_REGEX = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


async def signup(
    interaction: discord.Interaction, user_to_signup: discord.Member, bot: commands.Bot
) -> None:
    if discord_id_exists(user_to_signup.id):
        await interaction.followup.send(
            f"User {user_to_signup.mention} already signed up"
        )
        return

    await interaction.followup.send(f"Sent {user_to_signup.mention} dm to register")
    await add_user(user_to_signup, bot)


def create_message_filter(
    user: discord.Member, dm_channel: discord.DMChannel
) -> Callable[[discord.Message], bool]:
    def message_filter(message: discord.Message) -> bool:
        return message.channel == dm_channel and message.author == user

    return message_filter


async def get_user_email(
    user: discord.Member, dm_channel: discord.DMChannel, bot: commands.Bot
) -> Optional[str]:
    await dm_channel.send(
        "\n".join(
            [
                "Welcome to task shaming!",
                "Please reply with your email",
                "*to stop signup, reply with 'q' at any time*",
            ]
        )
    )

    while True:
        try:
            reply = (
                await bot.wait_for(
                    "message",
                    check=create_message_filter(user, dm_channel),
                    timeout=SIGNUP_TIMEOUT,
                )
            ).content

        except asyncio.TimeoutError:
            await dm_channel.send("User signup timed out, please try again later")
            return None

        if reply == "q":
            await dm_channel.send("User signup cancelled")
            return None

        email_list = re.findall(EMAIL_REGEX, reply)

        if len(email_list) == 0:
            await dm_channel.send("No valid email provided, please try again")

        elif len(email_list) > 1:
            await dm_channel.send("Please provide only one email address")

        else:
            return email_list[0]


async def check_email_registration(
    user: discord.Member, dm_channel: discord.DMChannel, email: str
) -> bool:
    try:
        if not add_discord_to_user(email, user.id):
            return False
    except EmailClaimedError:
        await dm_channel.send(
            "This email is already registered, please try with another email"
        )

    await dm_channel.send("Todoist Linking complete!")
    logger.info("added user- user: %s, email: %s", user.name, email)
    return True


async def add_user(user: discord.Member, bot: commands.Bot) -> None:
    dm_channel = await user.create_dm()

    email = await get_user_email(user, dm_channel, bot)

    if not email:
        return

    logger.info("received email- user: %s, email: %s", user.name, email)

    if await check_email_registration(user, dm_channel, email):
        return

    await dm_channel.send(
        "\n".join(
            [
                "Please add the app to todoist and authorize it with the link in settings",
                f"{load_config().todoist.app_link}",
            ]
        )
    )

    for _ in range(10):
        # wait up to 10 minutes for user to add app

        try:
            reply = (
                await bot.wait_for(
                    "message",
                    check=create_message_filter(user, dm_channel),
                    timeout=ONE_MINUTE,
                )
            ).content

        except asyncio.TimeoutError:
            # check for updated config every minute
            pass

        else:
            if reply == "q":
                await dm_channel.send("User signup cancelled")
                return

        if await check_email_registration(user, dm_channel, email):
            return

    await dm_channel.send(
        "No authorization found for given email, please try again later"
    )
