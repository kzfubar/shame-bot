import logging
from http import HTTPStatus

import requests
from aiohttp import ClientError
from flask import Flask, Response, jsonify, request
from todoist_api_python.api import TodoistAPI

from utils.Config import load_config
from utils.Database import User, add_user, get_session, get_user_by_todoist_id

app = Flask(__name__)
logger = logging.getLogger(__name__)


@app.route("/connect", methods=["POST"])
def connect() -> tuple[Response, int]:
    config = load_config().todoist
    auth_url = f"https://todoist.com/oauth/authorize?client_id={config.client_id}&scope=data:read_write&state=yoink&redirect_uri={config.redirect_uri}"
    return jsonify(
        {
            "card": {
                "type": "AdaptiveCard",
                "body": [{"text": auth_url, "type": "TextBlock"}],
            }
        }
    ), HTTPStatus.OK


@app.route("/webhook", methods=["POST"])
def webhook() -> tuple[str, int]:
    data = request.json
    try:
        if data is None or "event_name" not in data:
            return "", HTTPStatus.BAD_REQUEST
        if data["event_name"] == "item:completed":
            task_id = data["event_data"]["id"]
            user_id = data["event_data"]["user_id"]
            with get_session() as session:
                user = get_user_by_todoist_id(session=session, todoist_id=user_id)
                if not user:
                    return "", HTTPStatus.BAD_REQUEST
                clear_shame(user.todoist_token, task_id)
    except Exception:
        logger.exception("Error processing webhook")
        return "", HTTPStatus.INTERNAL_SERVER_ERROR
    return "", HTTPStatus.OK


@app.route("/auth", methods=["GET"])
def auth() -> tuple[str, int]:
    code = request.args.get("code")
    if not code:
        return "No code provided", HTTPStatus.BAD_REQUEST
    access_token = exchange_code_for_token(code)
    user_id, user_email = get_user_info_from_todoist(access_token)
    with get_session() as session:
        if user_id and user_email:
            add_user(
                session=session,
                user=User(
                    email=user_email, todoist_id=user_id, todoist_token=access_token
                ),
            )
    return "Success", HTTPStatus.OK


def exchange_code_for_token(code: str) -> str:
    config = load_config().todoist

    response = requests.post(
        config.token_url,
        data={
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "code": code,
            "redirect_uri": config.redirect_uri,
        },
        timeout=10,
    )

    response_json = response.json()
    return response_json.get("access_token")


def get_user_info_from_todoist(access_token: str) -> tuple[str, str]:
    sync_url = "https://api.todoist.com/sync/v9/sync"
    headers = {"Authorization": f"Bearer {access_token}"}

    data = {"sync_token": "*", "resource_types": '["user"]'}

    response = requests.post(sync_url, headers=headers, data=data, timeout=10)

    if response.status_code == HTTPStatus.OK:
        response_json = response.json()
        user_info = response_json.get("user", {})
        user_id = user_info.get("id")
        user_email = user_info.get("email")
        return user_id, user_email
    raise ClientError


def clear_shame(token: str, completed_task_id: str) -> None:
    try:
        api = TodoistAPI(token)
        task = api.get_task(completed_task_id)
        if task is None or task.labels is None:
            return

        updated_labels = [label for label in task.labels if label != "shame"]
        success = api.update_task(task_id=completed_task_id, labels=updated_labels)

        if success:
            logger.info("Cleared shame on task %s", completed_task_id)
        else:
            logger.warning("Failed to clear shame on task %s", completed_task_id)
    except Exception:
        logger.exception("Failed to clear shame")


if __name__ == "__main__":
    app.run(port=5002)
