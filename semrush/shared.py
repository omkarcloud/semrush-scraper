"""Small helpers shared by the /semrush/* endpoint modules: the two domain
pages decoded once and remembered in-process for a while, so the sliced
endpoints (traffic / backlinks / sources / …) of one domain cost ONE
400 KB page download between them, not one each."""
import threading
import time

from semrush import parsers as P
from semrush import refs
from semrush.fetch import SemrushNotFound, SemrushUpstreamError, get_html

_PAGE_TTL = 30 * 60
_pages = {}
_lock = threading.Lock()

_COMPONENT = {"overview": "WebsiteView", "competitors": "CompetitorsView"}


def not_found(domain):
    hint = refs.root_domain_hint(domain)
    message = f"semrush has no page for '{domain}' (root domains with enough traffic only)"
    if hint:
        message += f"; try '{hint}'"
    return SemrushNotFound(message)


def page_props(domain, tab="overview"):
    """Decoded astro props of /website/<domain>/<tab>/ (memoized)."""
    key = (domain, tab)
    now = time.time()
    with _lock:
        hit = _pages.get(key)
        if hit and hit[1] > now:
            return hit[0]
    html = get_html(refs.website_link(domain, tab), label=f"website/{domain}/{tab}",
                    missing=str(not_found(domain)))
    props = P.astro_props(html, _COMPONENT.get(tab))
    if not props or not isinstance(props.get("page"), dict):
        P_dump = getattr(__import__("semrush.fetch", fromlist=["dump_debug"]), "dump_debug")
        P_dump("noprops", html)
        raise SemrushUpstreamError(f"website/{domain}/{tab}: page carries no data island")
    with _lock:
        _pages[key] = (props, now + _PAGE_TTL)
        if len(_pages) > 500:
            for stale in [k for k, v in _pages.items() if v[1] <= now][:100]:
                _pages.pop(stale, None)
    return props


def overview(domain):
    return P.parse_overview(page_props(domain, "overview"))


def competitors(domain):
    return P.parse_competitors(page_props(domain, "competitors"))
