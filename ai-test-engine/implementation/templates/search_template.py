BODY = """\
    from utils.web_actions import WebActions
    from pages.common_page import CommonPage
    wa = WebActions(page)
    locator = 'input[type="search"],input[name*="search" i],[role="searchbox"],input[placeholder*="search" i]'
    wa.send_text(locator, {param})
    wa.press_key(locator, "Enter")
"""

def render(param_name: str) -> str:
    return BODY.replace("{param}", param_name)
