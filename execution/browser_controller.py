import base64
import logging
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)
_browsers: dict = {}


class BrowserController:
    def __init__(self):
        self._pw = None
        self._browser = None
        self.page = None
        self.highlight = False  # Set by caller after launch

    def launch(self, headless: bool = False):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=headless,
            args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = self._browser.new_context(viewport={"width": 1280, "height": 720})
        self.page = ctx.new_page()
        logger.info("Browser launched (headless=%s)", headless)
        return self

    def navigate(self, url: str):
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        self.page.wait_for_timeout(1500)

    def get_page_elements(self) -> list:
        return self.page.evaluate("""
        () => {
            const result = [];
            const sel = 'a, button, input, select, textarea, [role="button"], [role="link"], [role="tab"], [role="menuitem"], label, h1, h2, h3, [onclick], [class*="btn"]';
            document.querySelectorAll(sel).forEach((el, idx) => {
                const rect = el.getBoundingClientRect();
                if (rect.width < 2 || rect.height < 2) return;
                const text = (el.innerText || el.value || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 120);
                const ariaLabel = el.getAttribute('aria-label') || '';
                const placeholder = el.getAttribute('placeholder') || '';
                if (!text && !el.id && !ariaLabel && !placeholder) return;
                result.push({
                    idx,
                    tag: el.tagName.toLowerCase(),
                    text: text.slice(0, 100),
                    id: el.id || '',
                    name: el.getAttribute('name') || '',
                    type: el.getAttribute('type') || '',
                    role: el.getAttribute('role') || '',
                    aria_label: ariaLabel,
                    placeholder: placeholder,
                    href: el.tagName === 'A' ? (el.getAttribute('href') || '') : '',
                    classes: (el.className || '').split(' ').filter(c => c.length > 1 && c.length < 30).slice(0, 4).join(' '),
                });
            });
            return result.slice(0, 80);
        }
        """)

    def _highlight(self, locator: str) -> None:
        """Briefly highlight element with red border for visual feedback."""
        if not self.highlight:
            return
        try:
            el = self.page.locator(locator).first
            self.page.evaluate(
                """el => {
                    const p = { o: el.style.outline, of: el.style.outlineOffset, bg: el.style.backgroundColor, tr: el.style.transition };
                    el.style.transition = 'all 0.15s ease';
                    el.style.outline = '3px solid #ff4136';
                    el.style.outlineOffset = '3px';
                    el.style.backgroundColor = 'rgba(255,65,54,0.15)';
                    setTimeout(() => {
                        el.style.outline = p.o;
                        el.style.outlineOffset = p.of;
                        el.style.backgroundColor = p.bg;
                        el.style.transition = p.tr;
                    }, 900);
                }""",
                el.element_handle(),
            )
            self.page.wait_for_timeout(600)
        except Exception:
            pass

    def execute_action(self, action: str, locator: str, value: str = "", timeout: int = 10000):
        if action == "navigate":
            self.page.goto(value or locator, wait_until="domcontentloaded", timeout=timeout)
        elif action == "click":
            self._highlight(locator)
            self.page.locator(locator).first.click(timeout=timeout)
        elif action == "fill":
            self._highlight(locator)
            self.page.locator(locator).first.fill(value, timeout=timeout)
        elif action == "fill_and_submit":
            self._highlight(locator)
            self.page.locator(locator).first.fill(value, timeout=timeout)
            self.page.locator(locator).first.press("Enter")
            # Wait for any navigation triggered by the submit
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                self.page.wait_for_timeout(500)
            except Exception:
                pass
        elif action in ("assert_visible", "assert_text"):
            self._highlight(locator)
            self.page.locator(locator).first.wait_for(state="visible", timeout=timeout)
        elif action == "select":
            self._highlight(locator)
            self.page.locator(locator).first.select_option(value, timeout=timeout)
        elif action == "hover":
            self._highlight(locator)
            self.page.locator(locator).first.hover(timeout=timeout)
        else:
            self._highlight(locator)
            self.page.locator(locator).first.click(timeout=timeout)
        self.page.wait_for_timeout(800)

    def screenshot_b64(self) -> str:
        return base64.b64encode(self.page.screenshot()).decode()

    def current_url(self) -> str:
        return self.page.url

    def get_page_title(self) -> str:
        return self.page.title()

    def is_alive(self) -> bool:
        """Return True if the browser and page are still usable."""
        try:
            return bool(self.page and not self.page.is_closed())
        except Exception:
            return False

    def close(self):
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
            logger.info("Browser closed")
        except Exception as e:
            logger.warning("Error closing browser: %s", e)


class BrowserDeadError(RuntimeError):
    """Raised when the browser process has died and cannot be recovered."""


def get_browser(run_id: str, headless: bool = False, highlight: bool = False) -> BrowserController:
    if run_id in _browsers:
        ctrl = _browsers[run_id]
        if ctrl.is_alive():
            return ctrl
        # Browser died unexpectedly — clean up, do NOT recreate
        logger.warning("Browser for run %s is dead — removing from registry", run_id)
        try:
            ctrl.close()
        except Exception:
            pass
        del _browsers[run_id]
        raise BrowserDeadError(f"Browser closed unexpectedly for run {run_id}")

    # Fresh browser for a new run
    ctrl = BrowserController()
    ctrl.launch(headless=headless)
    ctrl.highlight = highlight
    _browsers[run_id] = ctrl
    return ctrl


def close_browser(run_id: str):
    if run_id in _browsers:
        _browsers[run_id].close()
        del _browsers[run_id]
