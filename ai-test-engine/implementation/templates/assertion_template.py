BODY = """\
    page.get_by_text({param}, exact=False).first.scroll_into_view_if_needed()
    page.get_by_text({param}, exact=False).first.wait_for(state="visible", timeout=15000)
"""

def render(param_name: str) -> str:
    return BODY.replace("{param}", param_name)
