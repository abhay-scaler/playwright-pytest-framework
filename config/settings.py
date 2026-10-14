import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCREENSHOT_DIR = BASE_DIR / "screenshots"
REPORT_DIR = BASE_DIR / "reports"
LOG_DIR = BASE_DIR / "logs"
TRACE_DIR = BASE_DIR / "traces"
VIDEO_DIR = BASE_DIR / "videos"
# Matches pytest.ini's --alluredir=reports/allure-results. Not created eagerly
# below (unlike the other output dirs) - allure-pytest creates it itself the
# first time it writes a result.
ALLURE_RESULTS_DIR = REPORT_DIR / "allure-results"

for directory in [SCREENSHOT_DIR, REPORT_DIR, LOG_DIR, TRACE_DIR, VIDEO_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

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
