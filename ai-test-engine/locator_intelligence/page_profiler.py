import re
from urllib.parse import urlparse, parse_qs

# Parameters that indicate the same page type regardless of value
_IGNORED_PARAMS = {"q", "query", "search", "keyword", "s", "page", "p", "offset",
                   "limit", "sort", "order", "filter", "utm_source", "utm_medium",
                   "utm_campaign", "ref", "from", "fbclid", "gclid", "sessionid"}

_PAGE_TYPE_RULES = [
    # (url_pattern, title_pattern, page_type, page_key_template)
    (r"/cart|/basket|/bag", r"cart|basket|bag", "cart_page", "cart_page"),
    (r"/checkout", r"checkout|payment|billing", "checkout_page", "checkout_page"),
    (r"/login|/signin|/sign-in", r"login|sign.?in", "login_page", "login_page"),
    (r"/register|/signup|/sign-up", r"register|sign.?up|create.?account", "register_page", "register_page"),
    (r"/search|/find|/results", r"search|result|found", "search_results_page", "search_results_page"),
    (r"/product/|/item/|/p/|/detail", r"", "product_detail_page", "product_detail_page"),
    (r"/category/|/cat/|/c/|/collection", r"", "category_page", "category_page"),
    (r"/account|/profile|/dashboard", r"account|profile|dashboard|my.page", "account_page", "account_page"),
    (r"^/$|^/home$|^/index", r"home|welcome|top", "home_page", "home_page"),
]


def normalize_page_key(url: str, title: str = "", headings: list = None) -> dict:
    """
    Return page identity info: page_key, page_type, url_pattern.
    Groups similar URLs under the same logical page.
    """
    headings = headings or []
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "").replace(".", "_").lower()
    path = parsed.path.rstrip("/") or "/"

    # Try rule-based detection
    title_lower = title.lower()
    path_lower = path.lower()
    all_text = f"{path_lower} {title_lower} {' '.join(h.lower() for h in headings)}"

    for url_pattern, title_pattern, page_type, page_key in _PAGE_TYPE_RULES:
        url_match = bool(re.search(url_pattern, path_lower))
        title_match = not title_pattern or bool(re.search(title_pattern, all_text))
        if url_match and title_match:
            return {
                "page_key": page_key,
                "page_type": page_type,
                "url_pattern": url_pattern,
                "class_name": _page_key_to_class(page_key),
            }

    # Fallback: use domain + cleaned path
    clean_path = re.sub(r"[^a-z0-9]+", "_", path_lower).strip("_")[:30]
    fallback_key = f"{domain}_{clean_path}".strip("_") or domain
    return {
        "page_key": fallback_key,
        "page_type": "unknown",
        "url_pattern": path,
        "class_name": _page_key_to_class(fallback_key),
    }


def _page_key_to_class(page_key: str) -> str:
    return "".join(w.capitalize() for w in page_key.split("_") if w)
