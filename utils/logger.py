import logging
import os

from config.settings import LOG_DIR

# Set by pytest-xdist inside each worker process (e.g. "gw0", "gw1"); absent
# when running serially, in which case every log line still goes somewhere
# clearly labelled rather than silently defaulting to the flat log file.
WORKER_ID = os.environ.get("PYTEST_XDIST_WORKER", "main")


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        f"%(asctime)s - %(levelname)s - [{WORKER_ID}] - %(name)s - %(message)s"
    )

    worker_log_dir = LOG_DIR / WORKER_ID
    worker_log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(worker_log_dir / "framework.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.propagate = False
    return logger
