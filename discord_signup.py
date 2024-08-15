# This is a test file for a user sign-up flow.
# It requires the bot to be alive at all times, so I have not merged it into the main script (yet?)

import configparser
import os
import re
from typing import Callable, Optional
import asyncio
import discord
from discord.ext import commands

ONE_MINUTE = 60
SIGNUP_TIMEOUT = ONE_MINUTE * 10

# Read the settings.cfg file
config_path = os.path.join(os.path.dirname(__file__), "settings.cfg")
config = configparser.ConfigParser()
config.read(config_path)

# Add sections to config if they are missing
if "DISCORD_ID_BY_EMAIL" not in config:
    config["TODOIST_KEY_BY_EMAIL"] = {}

if "DISCORD_ID_BY_EMAIL" not in config:
    config["DISCORD_ID_BY_EMAIL"] = {}

with open(config_path, "w") as configfile:
    config.write(configfile)

# Load the Discord bot token and channel ID from the config file
try:
    DISCORD_TOKEN = config.get("DISCORD", "TOKEN")
    CHANNEL_ID = config.getint("DISCORD", "CHANNEL_ID")
    SERVER_ID = config.getint("DISCORD", "SERVER_ID")
    LAST_ONLINE = config.get("DISCORD", "LAST_ONLINE", fallback=None)
except (configparser.NoSectionError, configparser.NoOptionError) as _:
    print("Discord config set incorrectly")
    exit()

try:
    TODOIST_LINK = config.get("TODOIST_AUTH", "APP_LINK")
except (configparser.NoSectionError, configparser.NoOptionError) as _:
    print("Todoist App link not set")
    exit()


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(intents=intents, command_prefix="!")

EMAIL_REGEX = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


@bot.event
async def on_ready():
    print("Bot is ready")
    synced = await bot.tree.sync()
    print(synced)


@bot.tree.command(name="signup")
@discord.app_commands.describe(user_to_signup="Mention of user")
async def signup(interaction: discord.Interaction, user_to_signup: discord.Member):
    # The slash command gives a hint to the user about the mentions arg,
    # but it isn't directly consumed in the function

    config.read(config_path)
    existing_users = dict(config.items("DISCORD_ID_BY_EMAIL")).values()

    if str(user_to_signup.id) in existing_users:
        await interaction.response.send_message(
            f"User {user_to_signup.mention} already signed up"
        )
        return

    await interaction.response.send_message(
        f"Sent {user_to_signup.mention} dm to register"
    )
    await add_user(user_to_signup)


def create_message_filter(
    user: discord.Member, dm_channel: discord.DMChannel
) -> Callable[[discord.Message], bool]:
    def message_filter(message: discord.Message) -> bool:
        return message.channel == dm_channel and message.author == user

    return message_filter


async def get_user_email(
    user: discord.Member, dm_channel: discord.DMChannel
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
    # pull most recent config data ...should this be a db (yes)?
    config.read(config_path)

    if email not in dict(config["TODOIST_KEY_BY_EMAIL"]):
        return False

    await dm_channel.send("Todoist Linking complete!")
    print(f"added user- user: {user.name}, email: {email}")
    config["DISCORD_ID_BY_EMAIL"][email] = str(user.id)

    with open(config_path, "w") as configfile:
        config.write(configfile)

    return True


async def add_user(user: discord.Member) -> None:
    dm_channel = await user.create_dm()

    email = await get_user_email(user, dm_channel)

    if not email:
        return

    print(f"received email- user: {user.name}, email: {email}")

    if await check_email_registration(user, dm_channel, email):
        return

    await dm_channel.send(
        "\n".join(
            [
                "Please add the app to todoist and authorize it with the link in settings",
                f"{TODOIST_LINK}",
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

        if await check_email_registration(user, dm_channel, email):
            return

        if reply == "q":
            await dm_channel.send("User signup cancelled")
            return

    await dm_channel.send(
        "No authorization found for given email, please try again later"
    )


bot.run(DISCORD_TOKEN)
