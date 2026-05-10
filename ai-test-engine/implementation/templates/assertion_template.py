BODY = """\
    from utils.web_actions import WebActions
    from pages.common_page import CommonPage
    wa = WebActions(page)
    locator = CommonPage.text_by_value({param})
    wa.wait_for_visible(locator)
"""

def render(param_name: str) -> str:
    return BODY.replace("{param}", param_name)
