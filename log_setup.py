import logging
from logging.handlers import TimedRotatingFileHandler
import os
from requests.adapters import HTTPAdapter

# Configure logging

from typing import Dict

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

    FORMATS: Dict[int, str] = {
        logging.DEBUG: grey + LOG_FORMAT + reset,
        logging.INFO: grey + LOG_FORMAT + reset,
        logging.WARNING: yellow + LOG_FORMAT + reset,
        logging.ERROR: red + LOG_FORMAT + reset,
        logging.CRITICAL: bold_red + LOG_FORMAT + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(fmt=log_fmt, datefmt=DATE_FORMAT, style="{")
        return formatter.format(record)


# Create log directory if it doesn't exist
log_directory = "log"
if not os.path.exists(log_directory):
    os.makedirs(log_directory)


# change the behavior of the root logger so all other loggers inherit this behavior
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Set up handlers (applies to all loggers unless overridden)
log_file_path = os.path.join(log_directory, "shamebot.log")
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

request_logger = logging.getLogger("requests")


class LoggingAdapter(HTTPAdapter):
    def send(self, request, **kwargs):
        # Log the request details
        request_logger.info(
            "Request Details:\nMethod: %s\nURL: %s\nBody: %s",
            request.method,
            request.url,
            request.body or "None",
            # stacklevel=8
        )

        # Send the request
        response = super().send(request, **kwargs)

        # Log the response details
        request_logger.info(
            "Response Details:\nStatus: %d\nBody: %s",
            response.status_code,
            response.text or "None",
            # stacklevel=8
        )

        return response
