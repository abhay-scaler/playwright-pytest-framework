import pytest

from apps.web_search.pages.home_page import HomePage


@pytest.mark.smoke
@pytest.mark.ui
@pytest.mark.quarantined
def test_web_search(page, app_config):
    """Quarantined 2026-10-24: a hydration race in this test, not a site outage.

    `HomePage.open` waits only for `domcontentloaded`, so the click lands on
    playwright.dev's server-rendered search button before Algolia DocSearch has
    attached its handler; nothing opens, and the wait for the modal input times
    out after 15s. Clicking immediately failed 3/3 and clicking after a short
    settle opened the modal 3/3 - the selectors themselves are current.

    It still runs: `pytest -m quarantined`, and a separate non-blocking CI job.
    The evidence, owner and the conditions for returning it to the blocking gate
    are in DESIGN.md section 8, 'Quarantined tests'. Do not stabilise this with a
    fixed sleep, a longer timeout or an extra rerun.
    """
    home_page = HomePage(page, app_config)
    home_page.open()
    home_page.search("Playwright")
    assert home_page.results_visible()
