from __future__ import annotations

from typing import Literal, Optional

import allure
from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from core.app_config import AppConfig
from utils.helpers import take_screenshot

WaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]


class BasePage:
    def __init__(self, page: Page, config: Optional[AppConfig] = None):
        self.page = page
        self.config = config

    @allure.step("Navigate to {url}")
    def goto(self, url: str, wait_until: WaitUntil = "load") -> None:
        self.page.goto(url, wait_until=wait_until)

    @allure.step("Wait for URL {url}")
    def wait_for_url(self, url: str, timeout: int = 10000) -> None:
        self.page.wait_for_url(url, timeout=timeout)

    @allure.step("Click {selector}")
    def click(self, selector: str, timeout: int = 10000) -> None:
        self.page.locator(selector).click(timeout=timeout)

    @allure.step("Click link {name}")
    def click_role_link(self, name: str, timeout: int = 10000) -> None:
        # Separate from click() because a role-based Locator (get_by_role) isn't
        # reachable through a plain CSS/text selector string - Playwright's own
        # `role` parameter is a Literal[...] type, so it must be passed as a
        # literal at each call site rather than threaded through as a variable.
        self.page.get_by_role("link", name=name).click(timeout=timeout)

    @allure.step("Click button {name}")
    def click_role_button(self, name: str, timeout: int = 10000) -> None:
        self.page.get_by_role("button", name=name).click(timeout=timeout)

    @allure.step("Fill {selector} with {value}")
    def fill(self, selector: str, value: str) -> None:
        self.page.locator(selector).fill(value)

    def get_text(self, selector: str) -> str:
        # Not step-decorated: an internal read, not a user/business-visible
        # action on its own - decorating every small primitive (this,
        # is_visible, raw locator calls) buries the meaningful steps
        # (navigation, click, fill, verification) in noise.
        return self.page.locator(selector).inner_text()

    def is_visible(self, selector: str, timeout: int = 5000) -> bool:
        # Locator.is_visible(timeout=...) does NOT poll/retry despite the timeout
        # param - it's a single instantaneous check. wait_for() actually retries
        # until the element becomes visible (or the timeout elapses), which is
        # almost always what a caller passing a timeout actually wants.
        try:
            self.page.locator(selector).first.wait_for(state="visible", timeout=timeout)
        except PlaywrightTimeoutError:
            return False
        return True

    @allure.step("Take screenshot")
    def take_screenshot(self, name: Optional[str] = None) -> str:
        return take_screenshot(self.page, name=name)

    @allure.step("Verify page title is {title}")
    def expect_title(self, title: str, timeout: int = 5000) -> None:
        # Playwright's own expect() polls/retries until the title matches (or
        # timeout elapses) instead of checking once - see is_visible() above
        # for why a single instantaneous check is the wrong default here.
        expect(self.page).to_have_title(title, timeout=timeout)

    @allure.step("Dismiss interstitial {selector} if visible")
    def dismiss_if_visible(self, selector: str, timeout: int = 3000) -> None:
        """Click an interstitial (cookie/consent banner, promo modal) if it shows
        up within `timeout`; a no-op if it never appears. Safe to call
        unconditionally right after navigation."""
        locator = self.page.locator(selector)
        try:
            locator.wait_for(state="visible", timeout=timeout)
        except PlaywrightTimeoutError:
            return
        locator.click()
