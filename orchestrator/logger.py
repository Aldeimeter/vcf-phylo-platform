import os
import logging
import logging_loki


def setup_logging(job_id: str):
    logger = logging.getLogger("orchestrator")
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    logger.handlers = []

    loki_handler = logging_loki.LokiHandler(
        url="http://loki:3100/loki/api/v1/push",
        tags={"job_id": job_id, "service": "orchestrator"},
        version="1",
    )

    loki_level = os.environ.get("LOKI_LOG_LEVEL", "INFO").upper()
    loki_handler.setLevel(getattr(logging, loki_level, logging.INFO))

    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s - %(funcName)s:%(lineno)d"
    )
    console_handler.setFormatter(console_formatter)

    console_level = os.environ.get("CONSOLE_LOG_LEVEL", log_level).upper()
    console_handler.setLevel(getattr(logging, console_level, logging.INFO))

    logger.addHandler(loki_handler)
    logger.addHandler(console_handler)

    return logger
