from pytest_bdd import given, when, then
from playwright.sync_api import Page
from utils.page_analyzer import analyze_and_save


@given("the page is analyzed")
@when("the page is analyzed")
@then("the page is analyzed")
def analyze_page(page: Page):
    path = analyze_and_save(page)
    print(f"\nNIPACHAN_ANALYSIS: page analyzed → {path}", flush=True)
