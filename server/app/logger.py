import os
import logging
import logging_loki


def setup_logging():
    logger = logging.getLogger("fastapi_app")
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    logger.handlers = []

    loki_url = os.environ.get("LOKI_URL", "http://loki:3100")
    loki_handler = logging_loki.LokiHandler(
        url=f"{loki_url}/loki/api/v1/push",
        tags={"service": "fastapi"},
        version="1",
    )
    loki_level = os.environ.get("LOKI_LOG_LEVEL", "INFO").upper()
    loki_handler.setLevel(getattr(logging, loki_level, logging.INFO))

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s - %(funcName)s:%(lineno)d")
    )
    console_level = os.environ.get("CONSOLE_LOG_LEVEL", log_level).upper()
    console_handler.setLevel(getattr(logging, console_level, logging.INFO))

    logger.addHandler(loki_handler)
    logger.addHandler(console_handler)

    return logger


logger = setup_logging()
