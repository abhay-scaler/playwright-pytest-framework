import allure
from playwright.sync_api import Page

from apps.uitesting_playground.locators.home_page_locators import HomePageLocators
from core.app_config import AppConfig
from core.base_page import BasePage


class HomePage(BasePage):
    # Unlike BasePage, config is required here (not Optional) - open() reads
    # self.config.base_url unconditionally. The class-level redeclaration is
    # what actually narrows the inherited attribute's type for mypy -
    # overriding __init__ alone does not.
    config: AppConfig

    def __init__(self, page: Page, config: AppConfig) -> None:
        super().__init__(page, config)

    @allure.step("Open UI Testing Playground homepage")
    def open(self) -> None:
        self.goto(self.config.base_url, wait_until="domcontentloaded")

    @allure.step("Navigate to Dynamic ID page")
    def navigate_to_dynamic_id_page(self) -> None:
        self.click_role_link(HomePageLocators.DYNAMIC_ID_LINK)

    @allure.step("Navigate to Hidden Layers page")
    def navigate_to_hidden_layers_page(self) -> None:
        self.click_role_link(HomePageLocators.HIDDEN_LAYERS_LINK)

    @allure.step("Navigate to Load Delay page")
    def navigate_to_load_delay_page(self) -> None:
        self.click_role_link(HomePageLocators.LOAD_DELAY_LINK)

    @allure.step("Navigate to AJAX Data page")
    def navigate_to_ajax_data_page(self) -> None:
        self.click_role_link(HomePageLocators.AJAX_DATA_LINK)
