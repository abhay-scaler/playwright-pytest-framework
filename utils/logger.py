from __future__ import annotations

import logging
import os
from typing import Optional

from config import settings
from config.paths import ProjectRootError

# Set by pytest-xdist inside each worker process (e.g. "gw0", "gw1"); absent
# when running serially, in which case every log line still goes somewhere
# clearly labelled rather than silently defaulting to the flat log file.
WORKER_ID = os.environ.get("PYTEST_XDIST_WORKER", "main")

LOG_FILENAME = "framework.log"


class ProjectLogFileHandler(logging.Handler):
    """A file handler that decides *where* to write when the first record arrives.

    This module is imported while the root conftest is still being imported -
    that is, before `pytest_configure` can pin pytest's rootdir - so resolving
    the log directory when the handler is constructed would bind the logger to
    whatever root happened to be resolvable at import time. When those differ
    (a `$PWPF_ROOT` that disagrees with pytest's rootdir, say) the logs would go
    one way and every other artifact the other, silently. Deferring to the first
    emit means the directory is the one the session actually settled on.

    If no project root can be resolved at that point, file logging is skipped
    rather than raising: logging must never be the thing that breaks a run, and
    writing into the framework's own directory is exactly what must not happen.
    The stream handler keeps working either way.
    """

    def __init__(self) -> None:
        super().__init__()
        self._delegate: Optional[logging.FileHandler] = None
        self._unavailable = False

    def _file_handler(self) -> Optional[logging.FileHandler]:
        if self._delegate is not None or self._unavailable:
            return self._delegate
        try:
            # Looked up through the module rather than imported by name: this
            # module gets reloaded in tests while config.settings is patched,
            # and a by-name import would capture the patched function for the
            # rest of the process - the same early-capture problem one level up.
            directory = settings.ensure_dir(settings.log_dir() / WORKER_ID)
        except (ProjectRootError, OSError):
            self._unavailable = True
            return None
        self._delegate = logging.FileHandler(directory / LOG_FILENAME, encoding="utf-8")
        self._delegate.setFormatter(self.formatter)
        return self._delegate

    def emit(self, record: logging.LogRecord) -> None:
        handler = self._file_handler()
        if handler is not None:
            handler.emit(record)

    def setFormatter(self, fmt: Optional[logging.Formatter]) -> None:
        super().setFormatter(fmt)
        if self._delegate is not None:
            self._delegate.setFormatter(fmt)

    def close(self) -> None:
        if self._delegate is not None:
            self._delegate.close()
        super().close()


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        f"%(asctime)s - %(levelname)s - [{WORKER_ID}] - %(name)s - %(message)s"
    )

    file_handler = ProjectLogFileHandler()
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.propagate = False
    return logger
