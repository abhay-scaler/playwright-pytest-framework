from __future__ import annotations

import allure
from playwright.sync_api import Page

from apps.web_search.locators.home_page_locators import HomePageLocators
from core.app_config import AppConfig
from core.base_page import BasePage


class HomePage(BasePage):
    # Unlike BasePage, config is required here (not Optional) - every method
    # below reads self.config unconditionally, since this app has no
    # meaningful way to function without knowing its own base_url. The class-
    # level redeclaration is what actually narrows the inherited attribute's
    # type for mypy - overriding __init__ alone does not.
    config: AppConfig

    def __init__(self, page: Page, config: AppConfig) -> None:
        super().__init__(page, config)

    @allure.step("Open web_search homepage")
    def open(self) -> None:
        self.goto(self.config.base_url, wait_until="domcontentloaded")
        # No-op today (playwright.dev has no consent banner) but wired through
        # config.extra so an app that does need one (e.g. a site with a GDPR
        # cookie wall) can set "consent_selector" in its config without any
        # framework change. See core/base_page.dismiss_if_visible.
        consent_selector = self.config.extra.get("consent_selector")
        if consent_selector:
            self.dismiss_if_visible(consent_selector)

    @allure.step("Search for {query}")
    def search(self, query: str) -> None:
        self.click(HomePageLocators.SEARCH_BUTTON)
        self.page.locator(HomePageLocators.SEARCH_INPUT).wait_for(
            state="visible", timeout=self.config.action_timeout
        )
        self.fill(HomePageLocators.SEARCH_INPUT, query)

    @allure.step("Verify search results are visible")
    def results_visible(self) -> bool:
        return self.is_visible(HomePageLocators.RESULTS, timeout=self.config.action_timeout)
