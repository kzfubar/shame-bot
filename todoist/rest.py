import logging
from http import HTTPStatus

import aiohttp

from todoist.types import Filter, Label, Task

logger = logging.getLogger(__name__)

API_URL = "https://api.todoist.com/rest/v2/"


async def get_tasks(
    session: aiohttp.ClientSession, api_token: str, task_filter: Filter
) -> list[Task]:
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"{API_URL}tasks"

    logging.info(str(task_filter))

    async with session.get(
        url, headers=headers, params={"filter": str(task_filter)}
    ) as response:
        if response.status != HTTPStatus.OK:
            logger.error("Failed to retrieve tasks: %s", response.status)
            raise aiohttp.ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=f"Failed to retrieve tasks: {response.status}",
            )

        res: list[dict] = await response.json()

        if not isinstance(res, list):
            logger.error("Response is not a list: %s", type(res))
            raise TypeError("Response is not a list")

        return [Task(**task) for task in res]


async def get_task(
    session: aiohttp.ClientSession, api_token: str, task_id: str
) -> Task | None:
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"{API_URL}tasks/{task_id}"

    async with session.get(url, headers=headers) as response:
        if response.status != HTTPStatus.OK:
            logger.error("Failed to retrieve task: %s", response.status)
            raise aiohttp.ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=f"Failed to retrieve task: {response.status}",
            )
        return Task(**await response.json())


async def get_labels(session: aiohttp.ClientSession, api_token: str) -> list[Label]:
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"{API_URL}labels"

    async with session.get(url, headers=headers) as response:
        if response.status != HTTPStatus.OK:
            logger.error("Failed to retrieve labels: %s", response.status)
            raise aiohttp.ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=f"Failed to retrieve labels: {response.status}",
            )

        res: list[dict] = await response.json()

        if not isinstance(res, list):
            logger.error("Response is not a list: %s", type(res))
            raise TypeError("Response is not a list")

        return [Label(**label) for label in res]


async def create_label(
    session: aiohttp.ClientSession, api_token: str, label_name: str
) -> None:
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"{API_URL}labels"

    async with session.post(
        url, headers=headers, json={"name": label_name}
    ) as response:
        if response.status != HTTPStatus.OK:
            logger.error("Failed to create label: %s", response.status)
            raise aiohttp.ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=f"Failed to create label: {response.status}",
            )
    logger.info("Created label: %s", label_name)


async def update_task(
    session: aiohttp.ClientSession, api_token: str, task: Task, data: dict
) -> None:
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"{API_URL}tasks/{task.id}"

    async with session.post(url, headers=headers, json=data) as response:
        if response.status != HTTPStatus.OK:
            logger.error("Failed to update task: %s", response.status)
            raise aiohttp.ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=f"Failed to update task: {response.status}",
            )


async def add_label(
    session: aiohttp.ClientSession, api_token: str, tasks: list[Task], label_name: str
) -> None:
    labels = await get_labels(session, api_token)

    label_id = next((label.id for label in labels if label.name == label_name), None)

    if label_id is None:
        await create_label(session, api_token, label_name)

    for task in tasks:
        task_labels = task.labels or []
        if label_name in task_labels:
            continue

        task_labels.append(label_name)
        data = {"labels": task_labels}

        await update_task(session, api_token, task, data)
