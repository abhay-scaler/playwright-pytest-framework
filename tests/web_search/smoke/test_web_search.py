import pytest

from apps.web_search.pages.home_page import HomePage


@pytest.mark.smoke
@pytest.mark.ui
def test_web_search(page, app_config):
    home_page = HomePage(page, app_config)
    home_page.open()
    home_page.search("Playwright")
    assert home_page.results_visible()
