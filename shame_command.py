import logging

import aiohttp
import discord

from log_setup import trace_config
from todoist.rest import get_tasks
from todoist.types import Filter
from utils.Constants import DUE_TODAY
from utils.Database import get_session, get_user_by_discord_id

logger = logging.getLogger(__name__)


# Discord bot command to shame the user
async def shame(
    interaction: discord.Interaction, user_to_shame: discord.Member
) -> None:
    async with aiohttp.ClientSession(trace_configs=[trace_config]) as client_session:
        with get_session() as session:
            user = get_user_by_discord_id(session=session, discord_id=user_to_shame.id)

        if user is None:
            await interaction.followup.send(
                f"{user_to_shame.mention} is not signed up!"
            )
            return
        # Get the tasks with the "shame" label
        shame_filter = Filter(label="shame") & DUE_TODAY
        shame_tasks = await get_tasks(client_session, user.todoist_token, shame_filter)

        if not shame_tasks:
            await interaction.followup.send(
                f"{user_to_shame.mention} has nothing to be ashamed of!"
            )
            return

        task_list = "\n".join([task.content for task in shame_tasks])
        await interaction.followup.send(
            f"For shame {user_to_shame.mention}!\n{task_list}"
        )
