from __future__ import annotations

import shutil
from pathlib import Path

from pwpf.config.settings import allure_results_dir
from pwpf.utils.logger import get_logger

LOGGER = get_logger(__name__)


def clean_allure_results(results_dir: str | Path | None = None) -> int:
    """Remove Allure results left over from previous runs.

    allure-pytest never clears its own output directory - left alone, every
    run adds another UUID-named result per test, forever, so `allure serve`/
    `allure generate` ends up mixing this run's results with every unrelated
    run that ever happened on this machine. Returns the number of entries
    removed, so a caller can tell "nothing to clean" apart from "cleaned N".
    """
    # Resolved on call rather than in the signature's default, so importing
    # this module does not require a project root to exist yet.
    results_dir = Path(results_dir) if results_dir is not None else allure_results_dir()
    if not results_dir.exists():
        return 0

    removed = 0
    for entry in results_dir.iterdir():
        if entry.is_file():
            entry.unlink()
        else:
            shutil.rmtree(entry)
        removed += 1

    if removed:
        LOGGER.info("Cleared %d stale Allure result file(s) from %s", removed, results_dir)
    return removed
