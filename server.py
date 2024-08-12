import configparser
import os

import requests
from flask import Flask, request, jsonify
from todoist_api_python.api import TodoistAPI

app = Flask(__name__)
# Load configuration from the settings.cfg file
config_path = os.path.join(os.path.dirname(__file__), 'settings.cfg')
config = configparser.ConfigParser()
config.read(config_path)


@app.route('/connect', methods=['POST'])
def connect():
    client_id = config['TODOIST_AUTH']['CLIENT_ID']
    redirect_uri = config['TODOIST_AUTH']['REDIRECT_URI']
    auth_url = f"https://todoist.com/oauth/authorize?client_id={client_id}&scope=data:read_write&state=yoink&redirect_uri={redirect_uri}"
    return jsonify({
        "card": {
            "type": "AdaptiveCard",
            "body": [{
                "text": auth_url,
                "type": "TextBlock"
            }]
        }
    }), 200


@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print(data)

    if data['event_name'] == 'item:completed':
        task_id = data['event_data']['id']
        user_id = data['event_data']['user_id']
        token = get_auth_token(user_id)
        clear_shame(token, task_id)
    return '', 200


@app.route('/auth', methods=['GET'])
def auth():
    code = request.args.get('code')
    access_token = exchange_code_for_token(code)
    user_id, user_email = get_user_info_from_todoist(access_token)
    if user_id and user_email:
        add_user_info_to_config(user_id, user_email, access_token)
    return 'Success', 200


def exchange_code_for_token(code):
    client_id = config['TODOIST_AUTH']['CLIENT_ID']
    client_secret = config['TODOIST_AUTH']['CLIENT_SECRET']
    redirect_uri = config['TODOIST_AUTH']['REDIRECT_URI']
    token_url = config['TODOIST_AUTH']['TOKEN_URL']

    response = requests.post(token_url, data={
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'redirect_uri': redirect_uri
    })

    response_json = response.json()
    print(response_json)
    return response_json.get('access_token')


def get_user_info_from_todoist(access_token):
    sync_url = 'https://api.todoist.com/sync/v9/sync'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    data = {
        'sync_token': '*',
        'resource_types': '["user"]'
    }

    response = requests.post(sync_url, headers=headers, data=data)

    if response.status_code == 200:
        response_json = response.json()
        user_info = response_json.get('user', {})
        user_id = user_info.get('id')
        user_email = user_info.get('email')
        return user_id, user_email
    else:
        print(f"Failed to fetch user info: {response.status_code} - {response.text}")
        return None, None


def add_user_info_to_config(user_id, user_email, access_token):
    if 'TODOIST_KEY_BY_EMAIL' not in config:
        config['TODOIST_KEY_BY_EMAIL'] = {}
    config['TODOIST_KEY_BY_EMAIL'][user_email] = access_token

    if 'EMAIL_BY_TODOIST_ID' not in config:
        config['EMAIL_BY_TODOIST_ID'] = {}
    config['EMAIL_BY_TODOIST_ID'][user_id] = user_email

    with open(config_path, 'w') as configfile:
        config.write(configfile)


def get_auth_token(user_id):
    # Check if the user ID exists in the config
    if str(user_id) in config['EMAIL_BY_TODOIST_ID']:
        user_email = config['EMAIL_BY_TODOIST_ID'][str(user_id)]
        return config['TODOIST_KEY_BY_EMAIL'][str(user_email)]
    else:
        # Redirect to the Todoist OAuth authorization page
        return


def get_todoist_token(user_id):
    # Retrieve the token using the user_id from the appropriate section
    token = config['TODOIST_KEY_BY_EMAIL'].get(user_id)
    if not token:
        raise ValueError(f"No token found for user_id: {user_id}")

    return token


def clear_shame(token, completed_task_id):
    try:
        api = TodoistAPI(token)
        task = api.get_task(completed_task_id)
        if task is None:
            print(f"Task with ID {completed_task_id} not found.")
            return

        updated_labels = [label for label in task.labels if label != 'shame']
        success = api.update_task(task_id=completed_task_id, labels=updated_labels)

        if success:
            print("Label cleared successfully.")
        else:
            print("Failed to update task.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == '__main__':
    app.run(port=5002)
