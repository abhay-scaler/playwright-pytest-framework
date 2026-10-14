from __future__ import annotations

from pathlib import Path

from config.settings import SCREENSHOT_DIR
from utils.logger import get_logger

LOGGER = get_logger(__name__)


def _discover_screenshots(screenshot_dir: Path, since: float | None = None) -> list[Path]:
    """Recursively find every *.png under screenshot_dir, including per-app
    subdirectories (screenshots/<app_name>/<test_name>.png).

    `since` (a time.time()-style timestamp), when given, excludes files whose
    mtime predates it - this is what keeps a stale screenshot left over from
    a previous run out of the current run's report.
    """
    if not screenshot_dir.exists():
        return []
    files = sorted(screenshot_dir.rglob("*.png"))
    if since is not None:
        files = [f for f in files if f.stat().st_mtime >= since]
    return files


def _asset_name_for(screenshot_file: Path, screenshot_dir: Path) -> str:
    """Namespace the copied asset by its owning app-subdirectory so two apps'
    identically-named screenshots (e.g. two test_homepage.png) can't collide
    once they're copied into one flat assets/ directory."""
    try:
        rel_parts = screenshot_file.relative_to(screenshot_dir).parts
    except ValueError:
        rel_parts = (screenshot_file.name,)
    if len(rel_parts) > 1:
        return f"{rel_parts[0]}__{screenshot_file.name}"
    return screenshot_file.name


def embed_failure_screenshots(
    report_path: str | Path,
    screenshot_dir: str | Path = SCREENSHOT_DIR,
    since: float | None = None,
) -> int:
    """Embed every failure screenshot under screenshot_dir into the generated
    pytest-html report at report_path. Searches recursively, so per-app
    subdirectories are included. Returns the number of screenshots embedded,
    so a caller can tell a genuinely artifact-free run apart from a silent
    failure to find anything.
    """
    report_path = Path(report_path)
    screenshot_dir = Path(screenshot_dir)

    if not report_path.exists():
        LOGGER.warning("Report not found, skipping screenshot embed: %s", report_path)
        return 0

    screenshot_files = _discover_screenshots(screenshot_dir, since=since)
    if not screenshot_files:
        LOGGER.info("No failure screenshots found under %s to embed", screenshot_dir)
        return 0

    html = report_path.read_text(encoding="utf-8")
    assets_dir = report_path.parent / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    embedded = 0
    for screenshot_file in screenshot_files:
        asset_name = _asset_name_for(screenshot_file, screenshot_dir)
        asset_path = assets_dir / asset_name
        if not asset_path.exists():
            asset_path.write_bytes(screenshot_file.read_bytes())

        marker = (
            '<div style="margin-top: 16px; padding: 12px; border: 1px solid #d0d7de; '
            'border-radius: 6px; background: #f6f8fa;">'
            f'<strong style="display: block; margin-bottom: 8px;">'
            f"Failure Screenshot ({asset_name})</strong>"
            f'<img src="assets/{asset_name}" alt="failure screenshot" '
            'style="max-width: 100%; border: 1px solid #d0d7de;" />'
            "</div>"
        )

        if marker not in html:
            html = html.replace("</body>", f"{marker}\n</body>", 1)
            embedded += 1

    report_path.write_text(html, encoding="utf-8")
    LOGGER.info("Embedded %d failure screenshot(s) into %s", embedded, report_path)
    return embedded
