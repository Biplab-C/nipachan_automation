from pytest_bdd import when, parsers
from playwright.sync_api import Page


@when(parsers.parse('I search for "{search_term}"'))
def i_search_for_value(page: Page, search_term: str):
    box = page.locator(
        'input[type="search"], input[placeholder*="Search" i], [role="searchbox"], input[name*="search" i]'
    ).first
    box.fill(search_term)
    box.press("Enter")
