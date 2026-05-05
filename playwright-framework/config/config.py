import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent


class Config:
    # Browser
    BROWSER: str = os.getenv("BROWSER", "chromium")
    CHANNEL: str = os.getenv("CHANNEL", "")          # e.g. "msedge", "chrome"
    HEADLESS: bool = os.getenv("HEADLESS", "false").lower() == "true"
    SLOW_MO: int = int(os.getenv("SLOW_MO", "0"))
    TIMEOUT: int = int(os.getenv("TIMEOUT", "30000"))
    BASE_URL: str = os.getenv("BASE_URL", "https://www.amazon.com")

    # Visual debugging
    HIGHLIGHT_ELEMENTS: bool = os.getenv("HIGHLIGHT_ELEMENTS", "false").lower() == "true"

    # Retry
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY: float = float(os.getenv("RETRY_DELAY", "1.0"))

    # Database
    DB_URL: str = os.getenv("DB_URL", f"sqlite:///{BASE_DIR}/data/test.db")

    # Paths
    DATA_DIR: Path = BASE_DIR / "data"
    REPORTS_DIR: Path = BASE_DIR / "reports"
    SCREENSHOTS_DIR: Path = BASE_DIR / "reports" / "screenshots"
    HTML_REPORT_DIR: Path = BASE_DIR / "reports" / "html-report"
