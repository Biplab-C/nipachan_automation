"""Collects meaningful DOM elements from a live Playwright page."""

_COLLECT_JS = """
() => {
    const results = [];
    const seen = new Set();

    function getSelector(el) {
        if (el.getAttribute('data-testid')) return '[data-testid="' + el.getAttribute('data-testid') + '"]';
        if (el.getAttribute('data-test')) return '[data-test="' + el.getAttribute('data-test') + '"]';
        if (el.getAttribute('data-qa')) return '[data-qa="' + el.getAttribute('data-qa') + '"]';
        if (el.id) return '#' + el.id;
        return null;
    }

    function getBoundingBox(el) {
        const r = el.getBoundingClientRect();
        return { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) };
    }

    function getParentSummary(el) {
        const p = el.parentElement;
        if (!p) return null;
        return {
            tag: p.tagName.toLowerCase(),
            class: (p.className || '').split(' ').filter(c => c.length > 1 && c.length < 40).slice(0, 3).join(' '),
            id: p.id || ''
        };
    }

    function getText(el) {
        return (el.innerText || el.value || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 150);
    }

    function getSiblingCount(el) {
        if (!el.parentElement) return 0;
        const tag = el.tagName;
        const cls = (el.className || '').split(' ')[0];
        return Array.from(el.parentElement.children).filter(c => c.tagName === tag && (c.className || '').startsWith(cls)).length;
    }

    const sel = [
        'button', 'a[href]', 'input', 'textarea', 'select',
        '[role="button"]', '[role="link"]', '[role="tab"]', '[role="menuitem"]',
        '[role="checkbox"]', '[role="radio"]', '[role="combobox"]', '[role="listbox"]',
        'h1', 'h2', 'h3',
        '[data-testid]', '[data-test]', '[data-qa]',
        'label', 'form', '[type="submit"]', '[type="reset"]'
    ].join(', ');

    document.querySelectorAll(sel).forEach((el, idx) => {
        const bb = getBoundingBox(el);
        if (bb.width < 2 || bb.height < 2) return;

        const text = getText(el);
        const ariaLabel = el.getAttribute('aria-label') || '';
        const placeholder = el.getAttribute('placeholder') || '';
        const dataTestId = el.getAttribute('data-testid') || el.getAttribute('data-test') || el.getAttribute('data-qa') || '';

        if (!text && !el.id && !ariaLabel && !placeholder && !dataTestId) return;

        const key = el.tagName + '|' + text.slice(0, 40) + '|' + el.id;
        if (seen.has(key)) return;
        seen.add(key);

        const classes = (el.className || '').split(' ').filter(c => c.length > 1 && c.length < 40).slice(0, 5);

        results.push({
            idx,
            tag: el.tagName.toLowerCase(),
            text: text.slice(0, 150),
            id: el.id || '',
            name: el.getAttribute('name') || '',
            type: el.getAttribute('type') || '',
            role: el.getAttribute('role') || '',
            aria_label: ariaLabel,
            placeholder: placeholder,
            data_testid: dataTestId,
            href: el.tagName === 'A' ? (el.getAttribute('href') || '') : '',
            classes: classes,
            class_str: classes.join(' '),
            stable_selector: getSelector(el) || '',
            bounding_box: bb,
            parent_summary: getParentSummary(el),
            sibling_count: getSiblingCount(el),
            visible: true
        });
    });

    return results.slice(0, 120);
}
"""

_HEADING_JS = """
() => Array.from(document.querySelectorAll('h1,h2,h3')).map(h => h.innerText.trim()).filter(Boolean).slice(0, 10)
"""


def collect_elements(page) -> list[dict]:
    """Collect meaningful DOM elements from a live Playwright page."""
    try:
        elements = page.evaluate(_COLLECT_JS)
        return elements or []
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("DOM collection failed: %s", e)
        return []


def collect_headings(page) -> list[str]:
    """Collect visible heading texts."""
    try:
        return page.evaluate(_HEADING_JS) or []
    except Exception:
        return []
