import configparser
import logging
from http import HTTPStatus
from pathlib import Path

import requests
from aiohttp import ClientError
from flask import Flask, Response, jsonify, request
from todoist_api_python.api import TodoistAPI

app = Flask(__name__)
# Load configuration from the settings.cfg file
config_path = Path(__file__).parent / "settings.cfg"
config = configparser.ConfigParser()
config.read(config_path)

logger = logging.getLogger(__name__)


@app.route("/connect", methods=["POST"])
def connect() -> tuple[Response, int]:
    client_id = config["TODOIST_AUTH"]["CLIENT_ID"]
    redirect_uri = config["TODOIST_AUTH"]["REDIRECT_URI"]
    auth_url = f"https://todoist.com/oauth/authorize?client_id={client_id}&scope=data:read_write&state=yoink&redirect_uri={redirect_uri}"
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
            token = get_auth_token(user_id)
            clear_shame(token, task_id)
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
    if user_id and user_email:
        add_user_info_to_config(user_id, user_email, access_token)
    return "Success", HTTPStatus.OK


def exchange_code_for_token(code: str) -> str:
    client_id = config["TODOIST_AUTH"]["CLIENT_ID"]
    client_secret = config["TODOIST_AUTH"]["CLIENT_SECRET"]
    redirect_uri = config["TODOIST_AUTH"]["REDIRECT_URI"]
    token_url = config["TODOIST_AUTH"]["TOKEN_URL"]

    response = requests.post(
        token_url,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
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


def add_user_info_to_config(user_id: str, user_email: str, access_token: str) -> None:
    if "TODOIST_KEY_BY_EMAIL" not in config:
        config["TODOIST_KEY_BY_EMAIL"] = {}
    config["TODOIST_KEY_BY_EMAIL"][user_email] = access_token

    if "EMAIL_BY_TODOIST_ID" not in config:
        config["EMAIL_BY_TODOIST_ID"] = {}
    config["EMAIL_BY_TODOIST_ID"][user_id] = user_email

    with Path.open(config_path, "w", encoding="utf-8") as configfile:
        config.write(configfile)


def get_auth_token(user_id: int) -> str:
    # Check if the user ID exists in the config
    if str(user_id) in config["EMAIL_BY_TODOIST_ID"]:
        user_email = config["EMAIL_BY_TODOIST_ID"][str(user_id)]
        return config["TODOIST_KEY_BY_EMAIL"][str(user_email)]
    # Redirect to the Todoist OAuth authorization page
    msg = f"No token found for user_id: {user_id}"
    raise ValueError(msg)


def get_todoist_token(user_id: str) -> str:
    # Retrieve the token using the user_id from the appropriate section
    token = config["TODOIST_KEY_BY_EMAIL"].get(user_id)
    if not token:
        msg = f"No token found for user_id: {user_id}"
        raise ValueError(msg)

    return token


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
