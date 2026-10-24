import re

import allure
import pytest
from playwright.sync_api import expect

from apps.myntra.pages.home_page import HomePage


@pytest.mark.smoke
@pytest.mark.ui
@pytest.mark.production
def test_home_page_loads_successfully(page, app_config):
    """Myntra's homepage renders its own header search bar.

    `production`-marked: this drives a live third-party site, so it never runs in
    CI (see .github/workflows/ci.yml) and is opt-in locally with `-m production`.

    The title check is a cheap first gate only - an Akamai challenge or error page
    can carry "Myntra" in its title too, which is why the assertion that actually
    decides the outcome is the header search bar being present. An exact title
    string is deliberately not asserted: the live title read on 2026-10-24 was
    "Online Shopping for Women, Men, Kids Fashion & Lifestyle - Myntra", which a
    marketing change can rewrite without the homepage being any less healthy.
    """
    home_page = HomePage(page, app_config)
    home_page.open()
    with allure.step("Verify the page is Myntra's, not an error or bot-challenge page"):
        expect(page).to_have_title(re.compile(r"Myntra", re.IGNORECASE))
    assert home_page.search_bar_visible(), "Myntra homepage loaded without its header search bar"
