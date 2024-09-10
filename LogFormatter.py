import logging
from typing import Dict

LOG_FORMAT = (
    "%(asctime)s - %(name)20s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
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
        formatter = logging.Formatter(fmt=log_fmt, datefmt=DATE_FORMAT)
        return formatter.format(record)
