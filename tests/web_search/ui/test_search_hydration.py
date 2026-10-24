"""Regression cover for the hydration race in `HomePage.open`.

These run against a local HTML fixture, not playwright.dev: the interaction
contract is what is being tested - open the page, wait for it to become
interactive, click once, assert the modal really opened - and tying that to a
third party's uptime is what made the original smoke test unreliable in the
first place. `apps/web_search/testdata/hydration_fixture.html` reproduces the
defect deterministically by attaching the button's handler late.
"""

from dataclasses import replace

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect

from apps.web_search.locators.home_page_locators import HomePageLocators
from apps.web_search.pages.home_page import HomePage
from pwpf.config.paths import project_root
from pwpf.core.app_config import load_app_config

FIXTURE = project_root() / "apps" / "web_search" / "testdata" / "hydration_fixture.html"


def _fixture_config(hydrate: str, action_timeout: int = 5000):
    """The real web_search config, pointed at the local fixture.

    `replace` keeps every other field (and the app name, so failure artifacts
    still land under web_search/) instead of hand-building an AppConfig that
    could drift from the real schema.
    """
    return replace(
        load_app_config("web_search"),
        base_url=f"file://{FIXTURE}#hydrate={hydrate}",
        action_timeout=action_timeout,
    )


@pytest.mark.ui
def test_search_opens_the_modal_although_the_button_hydrates_late(page):
    """The button is visible and enabled 800ms before it does anything."""
    home_page = HomePage(page, _fixture_config("800"))
    home_page.open()
    home_page.search("Playwright")

    expect(page.locator(HomePageLocators.SEARCH_INPUT)).to_be_visible()
    expect(page.locator(HomePageLocators.SEARCH_INPUT)).to_have_value("Playwright")
    assert home_page.results_visible()


@pytest.mark.ui
def test_the_search_control_is_clicked_exactly_once(page):
    """The fixture's button toggles, like DocSearch's: a blind second click
    would close the modal the first one opened. One click, or this is wrong."""
    home_page = HomePage(page, _fixture_config("800"))
    home_page.open()
    home_page.search("Playwright")

    expect(page.locator(HomePageLocators.SEARCH_BUTTON)).to_have_attribute("data-clicks", "1")
    expect(page.locator(HomePageLocators.SEARCH_INPUT)).to_be_visible()


@pytest.mark.ui
def test_a_page_that_never_becomes_interactive_fails_loudly(page):
    """The point of waiting on a readiness signal is that an unhydrated page is
    a failure, not a silent pass: the old code clicked a dead button and timed
    out later, on a page that looked perfectly healthy in the screenshot."""
    home_page = HomePage(page, _fixture_config("never", action_timeout=1500))

    with pytest.raises(PlaywrightTimeoutError):
        home_page.open()

    expect(page.locator(HomePageLocators.SEARCH_INPUT)).not_to_be_visible()
