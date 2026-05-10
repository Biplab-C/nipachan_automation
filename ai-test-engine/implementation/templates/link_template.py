ASSERT_BODY = """\
    from utils.web_actions import WebActions
    from pages.common_page import CommonPage
    wa = WebActions(page)
    locator = CommonPage.link_by_text({param})
    wa.wait_for_visible(locator)
"""

CLICK_BODY = """\
    from utils.web_actions import WebActions
    from pages.common_page import CommonPage
    wa = WebActions(page)
    locator = CommonPage.link_by_text({param})
    wa.click(locator)
"""

def render_assertion(param_name: str) -> str:
    return ASSERT_BODY.replace("{param}", param_name)

def render_click(param_name: str) -> str:
    return CLICK_BODY.replace("{param}", param_name)
