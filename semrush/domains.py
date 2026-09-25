"""/semrush/domains/* — everything Semrush publishes about a root domain
on its public /website/<domain>/overview/ and /competitors/ pages (no
login, plain curl_cffi). Every function takes the kwargs its schema
(semrush/schemas.py) loads and returns the JSON body."""
from semrush import refs
from semrush import shared
from semrush.fetch import SemrushNotFound, run_parallel

_SLICES = ("traffic", "traffic_by_device", "traffic_by_country", "traffic_sources", "ai_traffic",
           "search_traffic", "top_keywords", "backlinks", "competitors", "site_audit", "related_domains")


def _head(overview):
    """Identity + headline stats, without the sliced blocks."""
    return {k: v for k, v in overview.items() if k not in _SLICES}


def overview(domain):
    """The whole overview page in one response."""
    return shared.overview(domain)


def rank(domain):
    """Rank triple, authority score and monthly visits only (a cheap
    DA-checker style call)."""
    return _head(shared.overview(domain))


def traffic(domain):
    data = shared.overview(domain)
    head = _head(data)
    return {**head, "traffic": data.get("traffic"), "traffic_by_device": data.get("traffic_by_device")}


def traffic_by_country(domain):
    data = shared.overview(domain)
    block = data.get("traffic_by_country") or {}
    return {**_head(data), "date": block.get("date"), "countries": block.get("countries") or []}


def traffic_sources(domain):
    data = shared.overview(domain)
    block = data.get("traffic_sources") or {}
    return {**_head(data), "date": block.get("date"), "incoming": block.get("incoming") or [],
            "outgoing": block.get("outgoing") or []}


def ai_traffic(domain):
    data = shared.overview(domain)
    block = data.get("ai_traffic") or {}
    return {**_head(data), "platforms": block.get("platforms") or [],
            "other_visits": block.get("other_visits"), "other_share_percent": block.get("other_share_percent")}


def search_traffic(domain):
    data = shared.overview(domain)
    return {**_head(data), "search_traffic": data.get("search_traffic")}


def top_keywords(domain):
    data = shared.overview(domain)
    block = data.get("top_keywords") or {}
    return {**_head(data), "date": block.get("date"), "keywords_country": block.get("country"),
            "keywords": block.get("keywords") or []}


def backlinks_overview(domain):
    data = shared.overview(domain)
    return {**_head(data), "backlinks": data.get("backlinks")}


def competitors(domain):
    """The competitors tab: the site and its 7 closest competitors with the
    full rank / authority / traffic / engagement profile each, plus the
    overview page's relevance-scored top 3."""
    page = shared.competitors(domain)
    try:
        top = (shared.overview(domain).get("competitors") or {}).get("competitors") or []
    except SemrushNotFound:
        top = []
    relevance = {c["domain"]: c.get("relevance_percent") for c in top if c.get("domain")}
    for c in page.get("competitors") or []:
        c["relevance_percent"] = relevance.get(c.get("domain"))
    return page


def related(domain):
    data = shared.overview(domain)
    return {**_head(data), "related_domains": data.get("related_domains") or {}}


def batch(domains):
    """Headline stats for up to 10 domains in one call (fetched in parallel);
    a domain without a page yields {"domain", "error"} instead of failing
    the batch."""
    def one(d):
        try:
            return rank(d)
        except SemrushNotFound as e:
            return {"domain": d, "link": refs.website_link(d), "error": str(e)}
    rows = run_parallel([lambda d=d: one(d) for d in domains])
    return {"count": len(rows), "domains": rows}
