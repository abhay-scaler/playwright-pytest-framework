import allure
import pytest
from playwright.sync_api import expect

from apps.sample_app.pages.sample_app_page import SampleAppPage


@pytest.mark.smoke
@pytest.mark.parametrize("name", ["Ava", "Playwright"])
def test_sample_app_greets_the_submitted_name(page, app_config, name):
    sample_page = SampleAppPage(page, app_config)
    sample_page.open()
    sample_page.enter_name(name)
    sample_page.submit()
    with allure.step(f"Verify greeting message is 'Hello, {name}!'"):
        expect(sample_page.message_locator()).to_have_text(f"Hello, {name}!")
