import logging
import logging.config
from typing import Optional


def configure_logging(log_format: str, log_level: Optional[str] = None) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "formatters": {"default": {"format": log_format}},
            "handlers": {
                "wsgi": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "default",
                }
            },
            "loggers": {"": {"level": log_level, "propagate": True}},
            "root": {"level": log_level or "INFO", "handlers": ["wsgi"]},
        }
    )


def get_logger() -> logging.Logger:
    return logging.getLogger()
