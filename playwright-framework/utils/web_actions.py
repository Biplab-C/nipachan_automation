import time
import logging
from typing import Any, List, Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config.config import Config

logger = logging.getLogger(__name__)


class WebActions:
    """
    Playwright web interaction utilities.
    Every public method retries up to MAX_RETRIES times with RETRY_DELAY between attempts.
    """

    def __init__(
        self,
        page: Page,
        max_retries: int = Config.MAX_RETRIES,
        retry_delay: float = Config.RETRY_DELAY,
    ):
        self.page = page
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    # ------------------------------------------------------------------
    # Element highlighting (visual debugging)
    # ------------------------------------------------------------------

    def _highlight(self, locator: str) -> None:
        """Briefly highlight an element with a red border before acting on it."""
        if not Config.HIGHLIGHT_ELEMENTS:
            return
        try:
            el = self.page.locator(locator).first
            self.page.evaluate(
                """el => {
                    const prev = { outline: el.style.outline, offset: el.style.outlineOffset, bg: el.style.backgroundColor, tr: el.style.transition };
                    el.style.transition = 'all 0.15s ease';
                    el.style.outline = '3px solid #ff4136';
                    el.style.outlineOffset = '3px';
                    el.style.backgroundColor = 'rgba(255,65,54,0.15)';
                    setTimeout(() => {
                        el.style.outline = prev.outline;
                        el.style.outlineOffset = prev.offset;
                        el.style.backgroundColor = prev.bg;
                        el.style.transition = prev.tr;
                    }, 900);
                }""",
                el.element_handle(),
            )
            self.page.wait_for_timeout(600)
        except Exception:
            pass  # Non-critical — never fail a test due to highlighting

    # ------------------------------------------------------------------
    # Core retry engine
    # ------------------------------------------------------------------

    def _execute_with_retry(self, action_name: str, action_func, *args, **kwargs) -> Any:
        """Execute action_func with up to max_retries attempts."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info("[Attempt %d/%d] %s", attempt, self.max_retries, action_name)
                result = action_func(*args, **kwargs)
                logger.info("[SUCCESS] %s", action_name)
                return result
            except Exception as exc:
                last_exc = exc
                logger.warning("[Attempt %d FAILED] %s — %s", attempt, action_name, exc)
                if attempt < self.max_retries:
                    logger.info("Retrying in %.1fs…", self.retry_delay)
                    time.sleep(self.retry_delay)
        raise RuntimeError(
            f"'{action_name}' failed after {self.max_retries} attempts. "
            f"Last error: {last_exc}"
        ) from last_exc

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, url: str) -> None:
        def _action():
            self.page.goto(url, wait_until="domcontentloaded")

        self._execute_with_retry(f"navigate('{url}')", _action)

    def refresh(self) -> None:
        def _action():
            self.page.reload(wait_until="domcontentloaded")

        self._execute_with_retry("refresh()", _action)

    # ------------------------------------------------------------------
    # Click actions
    # ------------------------------------------------------------------

    def click(self, locator: str, timeout: int = Config.TIMEOUT) -> None:
        self._highlight(locator)
        def _action():
            self.page.locator(locator).click(timeout=timeout)

        self._execute_with_retry(f"click('{locator}')", _action)

    def double_click(self, locator: str, timeout: int = Config.TIMEOUT) -> None:
        self._highlight(locator)
        def _action():
            self.page.locator(locator).dblclick(timeout=timeout)

        self._execute_with_retry(f"double_click('{locator}')", _action)

    def right_click(self, locator: str, timeout: int = Config.TIMEOUT) -> None:
        self._highlight(locator)
        def _action():
            self.page.locator(locator).click(button="right", timeout=timeout)

        self._execute_with_retry(f"right_click('{locator}')", _action)

    # ------------------------------------------------------------------
    # Text input
    # ------------------------------------------------------------------

    def send_text(
        self,
        locator: str,
        text: str,
        clear_first: bool = True,
        timeout: int = Config.TIMEOUT,
    ) -> None:
        self._highlight(locator)
        def _action():
            el = self.page.locator(locator)
            el.wait_for(state="visible", timeout=timeout)
            if clear_first:
                el.clear()
            el.fill(text)

        self._execute_with_retry(f"send_text('{locator}')", _action)

    def type_text(
        self,
        locator: str,
        text: str,
        delay: int = 50,
        timeout: int = Config.TIMEOUT,
    ) -> None:
        def _action():
            el = self.page.locator(locator)
            el.wait_for(state="visible", timeout=timeout)
            el.press_sequentially(text, delay=delay)

        self._execute_with_retry(f"type_text('{locator}')", _action)

    def press_key(self, locator: str, key: str, timeout: int = Config.TIMEOUT) -> None:
        def _action():
            self.page.locator(locator).press(key, timeout=timeout)

        self._execute_with_retry(f"press_key('{locator}', '{key}')", _action)

    def clear(self, locator: str, timeout: int = Config.TIMEOUT) -> None:
        def _action():
            self.page.locator(locator).clear(timeout=timeout)

        self._execute_with_retry(f"clear('{locator}')", _action)

    # ------------------------------------------------------------------
    # Getters
    # ------------------------------------------------------------------

    def get_text(self, locator: str, timeout: int = Config.TIMEOUT) -> str:
        def _action():
            el = self.page.locator(locator)
            el.wait_for(state="visible", timeout=timeout)
            return el.inner_text()

        return self._execute_with_retry(f"get_text('{locator}')", _action)

    def get_all_texts(self, locator: str) -> List[str]:
        def _action():
            return self.page.locator(locator).all_inner_texts()

        return self._execute_with_retry(f"get_all_texts('{locator}')", _action)

    def get_attribute(
        self, locator: str, attribute: str, timeout: int = Config.TIMEOUT
    ) -> Optional[str]:
        def _action():
            el = self.page.locator(locator)
            el.wait_for(state="attached", timeout=timeout)
            return el.get_attribute(attribute)

        return self._execute_with_retry(f"get_attribute('{locator}', '{attribute}')", _action)

    def get_title(self) -> str:
        def _action():
            return self.page.title()

        return self._execute_with_retry("get_title()", _action)

    def get_url(self) -> str:
        return self.page.url

    # ------------------------------------------------------------------
    # Waiting
    # ------------------------------------------------------------------

    def wait_for_visible(self, locator: str, timeout: int = Config.TIMEOUT) -> None:
        def _action():
            self.page.locator(locator).wait_for(state="visible", timeout=timeout)

        self._execute_with_retry(f"wait_for_visible('{locator}')", _action)

    def wait_for_hidden(self, locator: str, timeout: int = Config.TIMEOUT) -> None:
        def _action():
            self.page.locator(locator).wait_for(state="hidden", timeout=timeout)

        self._execute_with_retry(f"wait_for_hidden('{locator}')", _action)

    def wait_for_url(self, url_fragment: str, timeout: int = Config.TIMEOUT) -> None:
        def _action():
            self.page.wait_for_url(f"**{url_fragment}**", timeout=timeout)

        self._execute_with_retry(f"wait_for_url('{url_fragment}')", _action)

    # ------------------------------------------------------------------
    # Form controls
    # ------------------------------------------------------------------

    def select_option(
        self,
        locator: str,
        label: str = None,
        value: str = None,
        index: int = None,
        timeout: int = Config.TIMEOUT,
    ) -> None:
        self._highlight(locator)
        def _action():
            el = self.page.locator(locator)
            el.wait_for(state="visible", timeout=timeout)
            if label is not None:
                el.select_option(label=label)
            elif value is not None:
                el.select_option(value=value)
            elif index is not None:
                el.select_option(index=index)
            else:
                raise ValueError("Provide label, value, or index for select_option")

        self._execute_with_retry(f"select_option('{locator}')", _action)

    def check(self, locator: str, timeout: int = Config.TIMEOUT) -> None:
        self._highlight(locator)
        def _action():
            self.page.locator(locator).check(timeout=timeout)

        self._execute_with_retry(f"check('{locator}')", _action)

    def uncheck(self, locator: str, timeout: int = Config.TIMEOUT) -> None:
        self._highlight(locator)
        def _action():
            self.page.locator(locator).uncheck(timeout=timeout)

        self._execute_with_retry(f"uncheck('{locator}')", _action)

    def upload_file(self, locator: str, file_path: str, timeout: int = Config.TIMEOUT) -> None:
        self._highlight(locator)
        def _action():
            self.page.locator(locator).set_input_files(file_path, timeout=timeout)

        self._execute_with_retry(f"upload_file('{locator}')", _action)

    # ------------------------------------------------------------------
    # Mouse & scroll
    # ------------------------------------------------------------------

    def hover(self, locator: str, timeout: int = Config.TIMEOUT) -> None:
        self._highlight(locator)
        def _action():
            self.page.locator(locator).hover(timeout=timeout)

        self._execute_with_retry(f"hover('{locator}')", _action)

    def scroll_to_element(self, locator: str, timeout: int = Config.TIMEOUT) -> None:
        self._highlight(locator)
        def _action():
            self.page.locator(locator).scroll_into_view_if_needed(timeout=timeout)

        self._execute_with_retry(f"scroll_to_element('{locator}')", _action)

    def scroll_by(self, x: int = 0, y: int = 500) -> None:
        def _action():
            self.page.mouse.wheel(x, y)

        self._execute_with_retry(f"scroll_by({x}, {y})", _action)

    # ------------------------------------------------------------------
    # State checks (no retry — instant boolean checks)
    # ------------------------------------------------------------------

    def is_visible(self, locator: str, timeout: int = 5000) -> bool:
        try:
            return self.page.locator(locator).is_visible(timeout=timeout)
        except Exception:
            return False

    def is_enabled(self, locator: str) -> bool:
        try:
            return self.page.locator(locator).is_enabled()
        except Exception:
            return False

    def is_checked(self, locator: str) -> bool:
        try:
            return self.page.locator(locator).is_checked()
        except Exception:
            return False

    def count_elements(self, locator: str) -> int:
        try:
            return self.page.locator(locator).count()
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Screenshot & JS
    # ------------------------------------------------------------------

    def take_screenshot(self, path: str = None, full_page: bool = True) -> bytes:
        def _action():
            kwargs: dict = {"full_page": full_page}
            if path:
                kwargs["path"] = path
            return self.page.screenshot(**kwargs)

        return self._execute_with_retry("take_screenshot()", _action)

    def execute_script(self, script: str, *args) -> Any:
        def _action():
            return self.page.evaluate(script, *args)

        return self._execute_with_retry("execute_script()", _action)

    def accept_dialog(self) -> None:
        self.page.on("dialog", lambda dialog: dialog.accept())

    def dismiss_dialog(self) -> None:
        self.page.on("dialog", lambda dialog: dialog.dismiss())
