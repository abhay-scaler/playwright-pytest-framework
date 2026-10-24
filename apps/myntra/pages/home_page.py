from __future__ import annotations

import allure
from playwright.sync_api import Page

from apps.myntra.locators.home_page_locators import HomePageLocators
from core.app_config import AppConfig
from core.base_page import BasePage


class HomePage(BasePage):
    # config is required here (not Optional as on BasePage) - every method below
    # reads it, since the page has no meaningful behavior without knowing its own
    # base_url. Matches apps/web_search/pages/home_page.py exactly.
    config: AppConfig

    def __init__(self, page: Page, config: AppConfig) -> None:
        super().__init__(page, config)

    @allure.step("Open the Myntra homepage")
    def open(self) -> None:
        self.goto(self.config.base_url, wait_until="domcontentloaded")

    @allure.step("Check the header search bar is visible")
    def search_bar_visible(self) -> bool:
        return self.is_visible(HomePageLocators.SEARCH_INPUT, timeout=self.config.action_timeout)
