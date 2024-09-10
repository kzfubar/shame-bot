import configparser
import logging
import os
from typing import List

import aiohttp
import discord
from aiohttp import ClientResponseError

from Task import Task

logger = logging.getLogger(__name__)

# Load the config file
config_path = os.path.join(os.path.dirname(__file__), "settings.cfg")
config = configparser.ConfigParser()
config.read(config_path)

TODOIST_API = "https://api.todoist.com/rest/v2/tasks"


# Retrieve Todoist API Key for the email from the config file
def get_todoist_token(email: str) -> str:
    config.read(config_path)
    if email in config["TODOIST_KEY_BY_EMAIL"]:
        return config["TODOIST_KEY_BY_EMAIL"][email]
    else:
        return None


# Get tasks from Todoist API with 'shame' label using aiohttp
async def get_shame_tasks(
    todoist_token: str, session: aiohttp.ClientSession
) -> List[Task]:
    headers = {"Authorization": f"Bearer {todoist_token}"}
    params = {"filter": "label:shame"}

    async with session.get(TODOIST_API, headers=headers, params=params) as response:
        if response.status != 200:
            logger.error(f"Failed to retrieve tasks: {response.status}")
            raise ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=f"Failed to retrieve tasks: {response.status}",
            )
        return await response.json()


# Discord bot command to shame the user
async def shame(interaction: discord.Interaction, user_to_shame: discord.Member):
    config.read(config_path)
    # Find the email associated with the user
    email = next(
        (
            stored_email
            for stored_email, discord_id in config["DISCORD_ID_BY_EMAIL"].items()
            if discord_id == str(user_to_shame.id)
        ),
        None,
    )

    if email is None:
        await interaction.followup.send(f"{user_to_shame.mention} is not signed up!")
        return

    # Retrieve Todoist token for the email
    todoist_token = get_todoist_token(email)
    if todoist_token is None:
        await interaction.followup.send(
            f"No Todoist token found for {user_to_shame.mention}!"
        )
        return

    async with aiohttp.ClientSession() as session:
        # Get the tasks with the "shame" label
        shame_tasks = await get_shame_tasks(todoist_token, session)

        if not shame_tasks:
            await interaction.followup.send(
                f"{user_to_shame.mention} has nothing to be ashamed of!"
            )
            return

        task_list = "\n".join([task["content"] for task in shame_tasks])
        await interaction.followup.send(
            f"For shame {user_to_shame.mention}!\n{task_list}"
        )
