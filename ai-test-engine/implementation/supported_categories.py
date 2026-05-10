SUPPORTED = {
    "search",
    "link_assertion",
    "link_click",
    "button_click",
    "text_assertion",
    "form_input",
    "dropdown_select",
}

def is_supported(category: str) -> bool:
    return category in SUPPORTED
