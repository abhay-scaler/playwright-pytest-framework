from __future__ import annotations

from pathlib import Path

import allure
from playwright.sync_api import Locator

from apps.sample_app.locators.sample_app_locators import SampleAppLocators
from core.base_page import BasePage

# sample_app is a static local fixture, not a network service, so it resolves its
# own testdata path rather than using AppConfig.base_url (which stays empty for
# this app). Apps that talk to a real URL should use self.config.base_url instead.
TESTDATA_FILE = Path(__file__).resolve().parents[1] / "testdata" / "sample_app.html"


class SampleAppPage(BasePage):
    @allure.step("Open sample app page")
    def open(self) -> None:
        self.goto(f"file://{TESTDATA_FILE}")

    @allure.step("Enter name {name}")
    def enter_name(self, name: str) -> None:
        self.fill(SampleAppLocators.NAME_INPUT, name)

    @allure.step("Submit the form")
    def submit(self) -> None:
        self.click(SampleAppLocators.SUBMIT_BUTTON)

    def message_locator(self) -> Locator:
        # Returns the Locator itself (not the extracted text) so the test can
        # assert with Playwright's auto-retrying expect(...).to_have_text(...)
        # instead of a single non-retrying snapshot read.
        return self.page.locator(SampleAppLocators.MESSAGE)
