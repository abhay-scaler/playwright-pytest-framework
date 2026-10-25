from __future__ import annotations

import re
from pathlib import Path

from pwpf.config.settings import allure_results_dir
from pwpf.utils.logger import get_logger

LOGGER = get_logger(__name__)

# Every file allure-pytest writes into its results directory is flat and
# UUID-prefixed (`allure_commons/model2.py`, verified against allure-pytest
# 2.16): `{uuid}-result.json`, `{uuid}-container.json`, `{uuid}-globals.json`
# and `{uuid}-attachment.{ext}`. It creates no subdirectories.
#
# Anything else in there belongs to someone else. `environment.properties`,
# `executor.json`, `categories.json` and `history/` are *inputs* to
# `allure generate` that a project or its CI places deliberately, and a
# consumer may point `--alluredir` at a directory it shares with other files,
# so this removes only what matches below and never touches a directory.
#
# The trade-off is deliberate: if a future Allure renames its output, this stops
# recognising it and results accumulate - visible in the report, and fixed by
# updating this pattern - rather than deleting files that were never ours.
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
ALLURE_ARTIFACT = re.compile(
    rf"^{_UUID}-(?:result|container|globals)\.json$|^{_UUID}-attachment\.[A-Za-z0-9]+$",
    re.IGNORECASE,
)


def clean_allure_results(results_dir: str | Path | None = None) -> int:
    """Remove this Allure results directory's leftovers from previous runs.

    allure-pytest never clears its own output - left alone, every run adds
    another UUID-named result per test, forever, so `allure serve`/`allure
    generate` ends up mixing this run's results with every unrelated run that
    ever happened on this machine.

    Only Allure's own artefacts are removed (see `ALLURE_ARTIFACT`); unrelated
    files, nested directories and report inputs such as `environment.properties`
    are left exactly where they are. Returns the number of files removed, so a
    caller can tell "nothing to clean" apart from "cleaned N".

    `results_dir` is the directory to clean. Called without one it falls back to
    the framework's `allure_results_dir()` convention under the consumer's
    project root - fine for a deliberate call, which is why the plugin passes
    the directory this run is actually configured to write to instead.
    """
    # Resolved on call rather than in the signature's default, so importing
    # this module does not require a project root to exist yet.
    results_dir = Path(results_dir) if results_dir is not None else allure_results_dir()
    if not results_dir.is_dir():
        return 0

    # Clearing stale results is housekeeping, and housekeeping must not be able
    # to end a test run. Before this was guarded, one unwritable results
    # directory - a CI volume, a directory owned by another user - raised out of
    # `pytest_configure` and the session died with an INTERNALERROR before
    # collecting anything. Each failure is now reported and the rest proceeds;
    # `OSError` only, so a bug in this module still surfaces as a crash.
    try:
        entries = sorted(results_dir.iterdir())
    except OSError as error:
        LOGGER.warning("Could not read the Allure results directory %s: %s", results_dir, error)
        return 0

    removed = 0
    failed = 0
    for entry in entries:
        if not (entry.is_file() and ALLURE_ARTIFACT.match(entry.name)):
            continue
        try:
            # unlink, never rmtree: for a symlink this removes the link and
            # leaves whatever it pointed at alone.
            entry.unlink()
        except OSError as error:
            failed += 1
            LOGGER.warning("Could not remove the stale Allure result %s: %s", entry, error)
            continue
        removed += 1

    if removed:
        LOGGER.info("Cleared %d stale Allure result file(s) from %s", removed, results_dir)
    if failed:
        LOGGER.warning(
            "Left %d stale Allure result file(s) in %s that could not be removed; "
            "this run's results will be mixed with them",
            failed,
            results_dir,
        )
    return removed
