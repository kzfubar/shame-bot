import logging
from http import HTTPStatus
from typing import List

import aiohttp
import discord
from aiohttp import ClientResponseError
from todoist_api_python.models import Task

from log_setup import trace_config
from utils.Constants import OWNED_DUE_TODAY
from utils.Database import get_user_by_discord_id

logger = logging.getLogger(__name__)

TODOIST_API = "https://api.todoist.com/rest/v2/tasks"


# Get tasks from Todoist API with 'shame' label using aiohttp
async def get_shame_tasks(
    todoist_token: str, session: aiohttp.ClientSession
) -> List[Task]:
    headers = {"Authorization": f"Bearer {todoist_token}"}
    params = {"filter": f"label:shame & {OWNED_DUE_TODAY}"}

    async with session.get(TODOIST_API, headers=headers, params=params) as response:
        if response.status != HTTPStatus.OK:
            logger.error("Failed to retrieve tasks: %s", response.status)
            raise ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=f"Failed to retrieve tasks: {response.status}",
            )
        res = await response.json()
        return [Task.from_dict(task) for task in res]


# Discord bot command to shame the user
async def shame(
    interaction: discord.Interaction, user_to_shame: discord.Member
) -> None:
    user = get_user_by_discord_id(user_to_shame.id)

    if user is None:
        await interaction.followup.send(f"{user_to_shame.mention} is not signed up!")
        return

    async with aiohttp.ClientSession(trace_configs=[trace_config]) as session:
        # Get the tasks with the "shame" label
        shame_tasks = await get_shame_tasks(user.todoist_token, session)

        if not shame_tasks:
            await interaction.followup.send(
                f"{user_to_shame.mention} has nothing to be ashamed of!"
            )
            return

        task_list = "\n".join([task.content for task in shame_tasks])
        await interaction.followup.send(
            f"For shame {user_to_shame.mention}!\n{task_list}"
        )
