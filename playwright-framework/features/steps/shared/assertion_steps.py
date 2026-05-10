from pytest_bdd import then, parsers
from playwright.sync_api import Page


@then(parsers.parse('I verify "{text}" is visible'))
def i_verify_text_is_visible(page: Page, text: str):
    page.wait_for_load_state("domcontentloaded")
    el = page.get_by_text(text, exact=False).first
    el.scroll_into_view_if_needed()
    el.wait_for(state="visible", timeout=15000)
