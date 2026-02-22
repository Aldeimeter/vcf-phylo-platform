import logging
import logging_loki


def setup_logging(job_id: str):
    logger = logging.getLogger("orchestrator")
    logger.setLevel(logging.INFO)

    logger.handlers = []

    loki_handler = logging_loki.LokiHandler(
        url="http://loki:3100/loki/api/v1/push",
        tags={"job_id": job_id, "service": "orchestrator"},
        version="1",
    )

    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    console_handler.setFormatter(console_formatter)

    logger.addHandler(loki_handler)
    logger.addHandler(console_handler)

    return logger
