from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page

from config.settings import ensure_dir, screenshot_dir


def take_screenshot(page: Page, name: Optional[str] = None) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_name = name or f"screenshot_{timestamp}"
    # The directory is created here, when a screenshot is actually taken,
    # rather than as a side effect of importing the settings module.
    path = ensure_dir(screenshot_dir()) / f"{screenshot_name}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def read_text_file(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")
