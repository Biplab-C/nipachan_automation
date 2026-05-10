from pytest_bdd import when, parsers
from playwright.sync_api import Page


@when(parsers.parse('I enter "{value}" into "{field_name}"'))
def i_enter_value_into_field(page: Page, value: str, field_name: str):
    page.get_by_label(field_name, exact=False).first.fill(value)


@when(parsers.parse('I click "{button_text}" button'))
def i_click_button(page: Page, button_text: str):
    page.get_by_role("button", name=button_text).first.click()
