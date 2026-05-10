class CommonPage:

    @staticmethod
    def _escape_xpath_text(text: str) -> str:
        if "'" not in text:
            return f"'{text}'"
        if '"' not in text:
            return f'"{text}"'
        # Contains both ' and " — use concat()
        parts = text.split("'")
        concat_args = ", \"'\", ".join(f"'{p}'" for p in parts)
        return f"concat({concat_args})"

    @staticmethod
    def link_by_text(text: str) -> str:
        escaped = CommonPage._escape_xpath_text(text)
        return f"xpath=//a[normalize-space()={escaped} or contains(normalize-space(), {escaped})]"

    @staticmethod
    def button_by_text(text: str) -> str:
        escaped = CommonPage._escape_xpath_text(text)
        return (
            f"xpath=//button[normalize-space()={escaped} or contains(normalize-space(), {escaped})]"
            f" | xpath=//*[@role='button'][normalize-space()={escaped} or contains(normalize-space(), {escaped})]"
        )

    @staticmethod
    def text_by_value(text: str) -> str:
        escaped = CommonPage._escape_xpath_text(text)
        return f"xpath=//*[normalize-space()={escaped} or contains(normalize-space(), {escaped})]"
