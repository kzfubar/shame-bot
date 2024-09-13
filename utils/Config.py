import configparser
import logging
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read("settings.cfg")


@dataclass
class DiscordConfig:
    token: str
    channel_id: int
    server_id: int


@dataclass
class TodoistConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    token_url: str
    app_link: str


@dataclass
class ConfigValues:
    discord: DiscordConfig
    todoist: TodoistConfig


_config = None


def load_config() -> ConfigValues:
    global _config  # noqa: PLW0603
    if _config is not None:
        return _config
    try:
        discord_config = DiscordConfig(
            token=config.get("DISCORD", "TOKEN"),
            channel_id=config.getint("DISCORD", "CHANNEL_ID"),
            server_id=config.getint("DISCORD", "SERVER_ID"),
        )

    except (configparser.NoSectionError, configparser.NoOptionError):
        logger.exception("Discord config set incorrectly")
        sys.exit()

    try:
        todoist_config = TodoistConfig(
            client_id=config.get("TODOIST_AUTH", "CLIENT_ID"),
            client_secret=config.get("TODOIST_AUTH", "CLIENT_SECRET"),
            redirect_uri=config.get("TODOIST_AUTH", "REDIRECT_URI"),
            token_url=config.get("TODOIST_AUTH", "TOKEN_URL"),
            app_link=config.get("TODOIST_AUTH", "APP_LINK"),
        )

    except (configparser.NoSectionError, configparser.NoOptionError):
        logger.exception("Todoist config set incorrectly")
        sys.exit()

    _config = ConfigValues(discord=discord_config, todoist=todoist_config)
    return _config
