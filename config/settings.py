import os
from pathlib import Path

from config.paths import project_root

# Artifact locations, relative to the consumer project's root. They are
# functions rather than module-level constants for two reasons: the root is not
# knowable at import time (pytest has not told us its rootdir yet), and a
# constant computed from this file's location is exactly the assumption that
# breaks once the framework is installed as a package. The directories are not
# created here either - importing a settings module should not touch the
# filesystem; whoever writes an artifact creates its directory first.


def screenshot_dir() -> Path:
    return project_root() / "screenshots"


def report_dir() -> Path:
    return project_root() / "reports"


def log_dir() -> Path:
    return project_root() / "logs"


def trace_dir() -> Path:
    return project_root() / "traces"


def video_dir() -> Path:
    return project_root() / "videos"


def allure_results_dir() -> Path:
    # Matches pytest.ini's --alluredir=reports/allure-results. allure-pytest
    # creates it itself the first time it writes a result.
    return report_dir() / "allure-results"


def ensure_dir(path: Path) -> Path:
    """Create an artifact directory at the moment it is needed, not before."""
    path.mkdir(parents=True, exist_ok=True)
    return path


CI_ENV = os.getenv("CI", "").lower() in {"1", "true", "yes", "on"}
HEADLESS_ENV = os.getenv("HEADLESS")
HEADLESS = str(HEADLESS_ENV).lower() == "true" if HEADLESS_ENV is not None else CI_ENV

# BASE_URL is a legacy global fallback kept for backward compatibility. Applications
# no longer read it directly — each app defines its own base_url in
# apps/<app_name>/config/<environment>.json instead (see core/app_config.py).
BASE_URL = os.getenv("BASE_URL", "file://")
BROWSER_NAME = os.getenv("BROWSER", "chromium").lower()
ACTION_TIMEOUT = int(os.getenv("ACTION_TIMEOUT", "10000"))
RETRY_COUNT = int(os.getenv("RETRY_COUNT", "0"))
# Selects which per-app config file to load (apps/<app>/config/<ENVIRONMENT>.json).
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
