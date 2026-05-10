BODY = """\
    from utils.web_actions import WebActions
    from pages.common_page import CommonPage
    wa = WebActions(page)
    locator = CommonPage.button_by_text({param})
    wa.click(locator)
"""

def render(param_name: str) -> str:
    return BODY.replace("{param}", param_name)
