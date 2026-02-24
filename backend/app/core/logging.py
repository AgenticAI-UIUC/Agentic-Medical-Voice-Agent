import logging
from logging.config import dictConfig


def setup_logging() -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                },
                "uvicorn_default": {
                    "()": "uvicorn.logging.DefaultFormatter",
                    "fmt": "%(levelprefix)s %(message)s",
                    "use_colors": None,
                },
                "uvicorn_access": {
                    "()": "uvicorn.logging.AccessFormatter",
                    "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" '
                    "%(status_code)s",
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
                "uvicorn_default": {
                    "class": "logging.StreamHandler",
                    "formatter": "uvicorn_default",
                },
                "uvicorn_access": {
                    "class": "logging.StreamHandler",
                    "formatter": "uvicorn_access",
                },
            },
            "loggers": {
                "app": {"handlers": ["default"], "level": "INFO", "propagate": False},
                "uvicorn": {
                    "handlers": ["uvicorn_default"],
                    "level": "INFO",
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["uvicorn_default"],
                    "level": "INFO",
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["uvicorn_access"],
                    "level": "INFO",
                    "propagate": False,
                },
            },
            "root": {"handlers": ["default"], "level": "INFO"},
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
