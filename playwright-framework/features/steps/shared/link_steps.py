from pytest_bdd import when, then, parsers
from playwright.sync_api import Page


@then(parsers.parse('I verify "{link_text}" link is visible'))
def i_verify_link_is_visible(page: Page, link_text: str):
    page.get_by_role("link", name=link_text).first.wait_for(state="visible", timeout=30000)


@when(parsers.parse('I click "{link_text}" link'))
def i_click_link(page: Page, link_text: str):
    page.get_by_role("link", name=link_text).first.click()
