import os
import logging
import logging_loki
from queue import Queue


def _make_loki_queue_handler(service: str) -> logging_loki.LokiQueueHandler:
    loki_url = os.environ.get("LOKI_URL", "http://loki:3100")
    loki_level = os.environ.get("LOKI_LOG_LEVEL", "INFO").upper()
    handler = logging_loki.LokiQueueHandler(
        Queue(-1),
        url=f"{loki_url}/loki/api/v1/push",
        tags={"service": service},
        version="1",
    )
    handler.setLevel(getattr(logging, loki_level, logging.INFO))
    return handler


def _make_console_handler(log_level: str) -> logging.StreamHandler:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s - %(funcName)s:%(lineno)d")
    )
    console_level = os.environ.get("CONSOLE_LOG_LEVEL", log_level).upper()
    handler.setLevel(getattr(logging, console_level, logging.INFO))
    return handler


def setup_logging():
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    logger = logging.getLogger("fastapi_app")
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        logger.addHandler(_make_loki_queue_handler("fastapi"))
        logger.addHandler(_make_console_handler(log_level))

    return logger


class _DowngradeToDebug(logging.Filter):
    """Relabels every record to DEBUG so access logs appear at debug severity in Loki."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.levelno = logging.DEBUG
        record.levelname = "DEBUG"
        return True


def setup_access_logging():
    """Call this after Uvicorn has run its own dictConfig (e.g. from lifespan startup)."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    loki_handler = _make_loki_queue_handler("fastapi_access")
    loki_handler.addFilter(_DowngradeToDebug())

    console_handler = _make_console_handler(log_level)
    console_handler.addFilter(_DowngradeToDebug())

    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers = []
    access_logger.propagate = False
    access_logger.addHandler(loki_handler)
    access_logger.addHandler(console_handler)


logger = setup_logging()
