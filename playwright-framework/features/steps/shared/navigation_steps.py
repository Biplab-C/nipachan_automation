import os
from pytest_bdd import given
from playwright.sync_api import Page


@given("I am on the application home page")
def i_am_on_the_application_home_page(page: Page, app_url: str):
    page.goto(app_url, wait_until="domcontentloaded")
