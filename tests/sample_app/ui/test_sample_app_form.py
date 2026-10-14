import allure
import pytest
from playwright.sync_api import expect

from apps.sample_app.pages.sample_app_page import SampleAppPage


@pytest.mark.ui
def test_sample_app_form(page, app_config):
    sample_page = SampleAppPage(page, app_config)
    sample_page.open()
    sample_page.enter_name("Ava")
    sample_page.submit()
    with allure.step("Verify greeting message is 'Hello, Ava!'"):
        expect(sample_page.message_locator()).to_have_text("Hello, Ava!")
