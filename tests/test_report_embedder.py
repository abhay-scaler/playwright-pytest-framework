import os
import time

from utils.report_embedder import embed_failure_screenshots


def _make_report(tmp_path):
    report_path = tmp_path / "report.html"
    report_path.write_text("<html><body>original</body></html>", encoding="utf-8")
    return report_path


def _png_bytes() -> bytes:
    # Smallest possible valid PNG signature is enough - the embedder never
    # decodes the image, only copies bytes and links to them.
    return b"\x89PNG\r\n\x1a\n"


def test_flat_screenshot_is_embedded(tmp_path):
    report_path = _make_report(tmp_path)
    screenshot_dir = tmp_path / "screenshots"
    screenshot_dir.mkdir()
    (screenshot_dir / "test_flat.png").write_bytes(_png_bytes())

    embedded = embed_failure_screenshots(report_path, screenshot_dir)

    assert embedded == 1
    html = report_path.read_text(encoding="utf-8")
    assert "test_flat.png" in html
    assert (report_path.parent / "assets" / "test_flat.png").exists()


def test_app_nested_screenshot_is_discovered(tmp_path):
    """The bug this whole module exists to prevent regressing: a screenshot
    one directory deeper than the root must still be found and embedded."""
    report_path = _make_report(tmp_path)
    screenshot_dir = tmp_path / "screenshots"
    (screenshot_dir / "sample_app").mkdir(parents=True)
    (screenshot_dir / "sample_app" / "test_nested.png").write_bytes(_png_bytes())

    embedded = embed_failure_screenshots(report_path, screenshot_dir)

    assert embedded == 1
    html = report_path.read_text(encoding="utf-8")
    assert "sample_app__test_nested.png" in html
    assert (report_path.parent / "assets" / "sample_app__test_nested.png").exists()


def test_multiple_apps_all_embedded(tmp_path):
    report_path = _make_report(tmp_path)
    screenshot_dir = tmp_path / "screenshots"
    for app in ("sample_app", "web_search", "uitesting_playground"):
        app_dir = screenshot_dir / app
        app_dir.mkdir(parents=True)
        (app_dir / "test_smoke.png").write_bytes(_png_bytes())

    embedded = embed_failure_screenshots(report_path, screenshot_dir)

    assert embedded == 3
    html = report_path.read_text(encoding="utf-8")
    for app in ("sample_app", "web_search", "uitesting_playground"):
        assert f"{app}__test_smoke.png" in html


def test_multiple_tests_within_one_app_all_embedded(tmp_path):
    report_path = _make_report(tmp_path)
    screenshot_dir = tmp_path / "screenshots"
    app_dir = screenshot_dir / "sample_app"
    app_dir.mkdir(parents=True)
    for name in ("test_one", "test_two", "test_three[Ava]"):
        (app_dir / f"{name}.png").write_bytes(_png_bytes())

    embedded = embed_failure_screenshots(report_path, screenshot_dir)

    assert embedded == 3
    html = report_path.read_text(encoding="utf-8")
    assert "sample_app__test_one.png" in html
    assert "sample_app__test_two.png" in html
    assert "sample_app__test_three[Ava].png" in html


def test_no_screenshots_leaves_report_untouched(tmp_path):
    report_path = _make_report(tmp_path)
    original = report_path.read_text(encoding="utf-8")
    screenshot_dir = tmp_path / "screenshots"  # never created

    embedded = embed_failure_screenshots(report_path, screenshot_dir)

    assert embedded == 0
    assert report_path.read_text(encoding="utf-8") == original


def test_duplicate_filenames_across_apps_do_not_collide(tmp_path):
    report_path = _make_report(tmp_path)
    screenshot_dir = tmp_path / "screenshots"
    for app, marker in (("sample_app", b"AAAA"), ("web_search", b"BBBB")):
        app_dir = screenshot_dir / app
        app_dir.mkdir(parents=True)
        (app_dir / "test_homepage.png").write_bytes(_png_bytes() + marker)

    embedded = embed_failure_screenshots(report_path, screenshot_dir)

    assert embedded == 2
    assets_dir = report_path.parent / "assets"
    sample_bytes = (assets_dir / "sample_app__test_homepage.png").read_bytes()
    web_bytes = (assets_dir / "web_search__test_homepage.png").read_bytes()
    assert sample_bytes != web_bytes
    assert sample_bytes.endswith(b"AAAA")
    assert web_bytes.endswith(b"BBBB")


def test_stale_screenshot_excluded_by_since(tmp_path):
    """A screenshot older than `since` (left over from a previous run) must
    not be embedded into the current run's report. Backdates the stale
    file's mtime directly rather than sleeping, keeping the test fast and
    deterministic - matching this framework's no-hard-wait philosophy.
    """
    report_path = _make_report(tmp_path)
    screenshot_dir = tmp_path / "screenshots"
    screenshot_dir.mkdir()

    stale = screenshot_dir / "test_stale.png"
    stale.write_bytes(_png_bytes())
    one_hour_ago = time.time() - 3600
    os.utime(stale, (one_hour_ago, one_hour_ago))

    fresh = screenshot_dir / "test_fresh.png"
    fresh.write_bytes(_png_bytes())

    session_start = time.time() - 60  # well after the backdated stale file
    embedded = embed_failure_screenshots(report_path, screenshot_dir, since=session_start)

    assert embedded == 1
    html = report_path.read_text(encoding="utf-8")
    assert "test_fresh.png" in html
    assert "test_stale.png" not in html
