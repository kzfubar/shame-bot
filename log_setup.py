import logging
from http import HTTPStatus
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import ClassVar

import aiohttp

LOG_FORMAT = (
    "{asctime} - {name:15.15} - {levelname:8} - {message} ({filename}:{lineno})"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ColorFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    FORMATS: ClassVar[dict[int, str]] = {
        logging.DEBUG: grey + LOG_FORMAT + reset,
        logging.INFO: grey + LOG_FORMAT + reset,
        logging.WARNING: yellow + LOG_FORMAT + reset,
        logging.ERROR: red + LOG_FORMAT + reset,
        logging.CRITICAL: bold_red + LOG_FORMAT + reset,
    }

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(fmt=log_fmt, datefmt=DATE_FORMAT, style="{")
        return formatter.format(record)


def log_setup() -> None:
    # Create log directory if it doesn't exist
    log_directory = "log"
    if not Path(log_directory).exists:
        Path(log_directory).mkdir(parents=True)

    # change the behavior of the root logger so all other loggers inherit this behavior
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Set up handlers (applies to all loggers unless overridden)
    log_file_path = Path(log_directory) / "shamebot.log"
    file_handler = TimedRotatingFileHandler(
        log_file_path, when="midnight", interval=1, backupCount=7, utc=True
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT, style="{"))

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(ColorFormatter(style="{"))

    # Add handlers to the root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


request_logger = logging.getLogger("aiohttp")
trace_config = aiohttp.TraceConfig()


async def on_request_start(_, __, params: aiohttp.TraceRequestStartParams) -> None:  # noqa: RUF029
    request_logger.debug(
        "Request Started: %s %s", params.method, params.url, stacklevel=6
    )


async def on_request_end(_, __, params: aiohttp.TraceRequestEndParams) -> None:  # noqa: RUF029
    if params.response.status >= HTTPStatus.SERVICE_UNAVAILABLE:
        request_logger.error(
            "Request Error: %s %d",
            params.response.url,
            params.response.status,
            stacklevel=6,
        )
    else:
        request_logger.debug(
            "Response Received: %s %d",
            params.response.url,
            params.response.status,
            stacklevel=6,
        )


async def on_request_exception(  # noqa: RUF029
    _, __, params: aiohttp.TraceRequestExceptionParams
) -> None:
    request_logger.error("Request Exception: %s", params.exception, stacklevel=6)


trace_config.on_request_start.append(on_request_start)
trace_config.on_request_end.append(on_request_end)
trace_config.on_request_exception.append(on_request_exception)
