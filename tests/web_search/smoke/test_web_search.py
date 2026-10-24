import pytest

from apps.web_search.pages.home_page import HomePage


@pytest.mark.smoke
@pytest.mark.ui
def test_web_search(page, app_config):
    """Searching the docs returns results.

    Quarantined on 2026-10-24 for a hydration race, and repaired since:
    `HomePage.open` now waits for the site's own hydration flag before anything is
    clicked, so a click can no longer land on a button whose handler is not
    attached yet. The interaction contract itself is covered deterministically,
    without this third-party site, in tests/web_search/ui/test_search_hydration.py.
    """
    home_page = HomePage(page, app_config)
    home_page.open()
    home_page.search("Playwright")
    assert home_page.results_visible()
