from playwright.sync_api import Page


class BasePage:
    def __init__(self, page: Page, url: str = ""):
        self.page = page
        self._url = url

    def navigate_to(self) -> "BasePage":
        if self._url:
            self.page.goto(self._url, wait_until="domcontentloaded")
        return self
