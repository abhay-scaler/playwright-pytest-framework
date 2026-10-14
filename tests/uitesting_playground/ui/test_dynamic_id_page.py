import allure
import pytest
from playwright.sync_api import expect

from apps.uitesting_playground.pages.dynamic_id_page import DynamicIdPage
from apps.uitesting_playground.pages.home_page import HomePage


@pytest.mark.ui
def test_dynamic_id_button(page, app_config):
    homepage = HomePage(page, app_config)
    homepage.open()
    with allure.step("Verify homepage title is 'UI Test Automation Playground'"):
        expect(homepage.page).to_have_title("UI Test Automation Playground")
    homepage.navigate_to_dynamic_id_page()
    dynamic_id_page = DynamicIdPage(page, app_config)
    with allure.step("Verify Dynamic ID page title is 'Dynamic ID'"):
        expect(dynamic_id_page.page).to_have_title("Dynamic ID")
    dynamic_id_page.click_button()
