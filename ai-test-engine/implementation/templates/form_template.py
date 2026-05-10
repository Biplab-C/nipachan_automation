INPUT_BODY = """\
    from utils.web_actions import WebActions
    wa = WebActions(page)
    field_locator = f'[name*="{{{field_param}}}" i],[placeholder*="{{{field_param}}}" i],[aria-label*="{{{field_param}}}" i]'
    wa.send_text(field_locator, {value_param})
"""

DROPDOWN_BODY = """\
    from utils.web_actions import WebActions
    wa = WebActions(page)
    select_locator = f'select[name*="{{{field_param}}}" i],select[aria-label*="{{{field_param}}}" i]'
    wa.select_option(select_locator, label={value_param})
"""

def render_input(field_param: str, value_param: str) -> str:
    return INPUT_BODY.replace("{field_param}", field_param).replace("{value_param}", value_param)

def render_dropdown(field_param: str, value_param: str) -> str:
    return DROPDOWN_BODY.replace("{field_param}", field_param).replace("{value_param}", value_param)
