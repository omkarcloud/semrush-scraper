"""Semrush normalizers: the public pages' embedded JSON -> one clean
snake_case shape per entity.

Output conventions (shared with the other scrapers here): `link` for
canonical page URLs (always absolute), `*_count` for counters, `is_*` for
booleans, ISO dates (YYYY-MM-DD), numbers as numbers, null for missing.
Ratios Semrush stores as fractions (0.4112) are emitted as percentages
with a `_percent` suffix (41.12); durations in seconds carry `_seconds`.

Raw sources:
  * astro_props(html)       <astro-island props="…"> on /website/<d>/overview/
                            (component WebsiteView), /website/<d>/competitors/
                            (CompetitorsView) and /popular/<slug>/ (PopularView):
                            HTML-escaped JSON in Astro's [type, value] tuple
                            encoding (0 = scalar/object, 1 = array).
  * preloaded_state(html)   window.__PRELOADED_STATE__ on /trending-websites/…

Deliberately dropped as noise: `appProps.localeMessages` (the UI's i18n
strings), `page.meta` (SEO title/description), `page.isAuthorizedUser` /
`isBot` / `locale`, `noIndex`, each block's `visible` flag (a hidden block
is emitted as null), `trafficJourney.hosts` and the per-item `hosts[]`
(always the domain itself with share 1 for a root-domain page), the
`database` tag on every metric ("global" everywhere but the country
rank), the trending page's `complexity` (an undocumented internal
score), `i18n`, `featureFlags`, and every `siteAudit` block (all zeros
unless Semrush audited the site — emitted only when it did).
"""
import html as html_lib
import json
import re

from semrush import refs

# Semrush keyword intent codes (the official API's `In` column).
INTENTS = {"0": "commercial", "1": "informational", "2": "navigational", "3": "transactional"}


# ---- value helpers ---------------------------------------------------------------------

def to_int(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def to_float(value, digits=None):
    try:
        out = float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
    if out is not None and digits is not None:
        out = round(out, digits)
    return out


def percent(value):
    """A fraction (0.4112) -> a percentage (41.12); None stays None."""
    out = to_float(value)
    return round(out * 100, 2) if out is not None else None


def text(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def iso_date(value):
    """'2026-08-15' / '2026-08-01T00:00:00' -> 'YYYY-MM-DD'."""
    value = text(value)
    if not value:
        return None
    match = re.match(r"(\d{4}-\d{2}-\d{2})", value)
    return match.group(1) if match else None


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


# ---- raw extraction ----------------------------------------------------------------------

def _decode_astro(value):
    """Astro serializes island props as [type, value] tuples: 0 = plain
    value (object / scalar), 1 = array, 2 = Date, 3 = RegExp, 4 = Map,
    5 = Set, 6 = BigInt, 7 = URL. Only 0 / 1 appear on these pages."""
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], int) and 0 <= value[0] <= 7:
        kind, inner = value
        if kind == 1:
            return [_decode_astro(x) for x in _list(inner)]
        if kind in (4, 5):
            return [_decode_astro(x) for x in _list(inner)]
        return _decode_astro(inner)
    if isinstance(value, dict):
        return {k: _decode_astro(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode_astro(x) for x in value]
    return value


def astro_props(page_html, component=None):
    """The decoded props of the page's astro-island (optionally the one
    with `component-export=<component>`). None when absent."""
    if not page_html:
        return None
    pattern = r'<astro-island\b[^>]*?props="([^"]*)"'
    if component:
        pattern = r'<astro-island\b[^>]*component-export="' + re.escape(component) + r'"[^>]*props="([^"]*)"'
    match = re.search(pattern, page_html)
    if not match:
        return None
    try:
        raw = json.loads(html_lib.unescape(match.group(1)))
    except ValueError:
        return None
    return _decode_astro(raw)


def preloaded_state(page_html):
    """window.__PRELOADED_STATE__ = {...}; -> dict, or None."""
    if not page_html:
        return None
    match = re.search(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>", page_html, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        return None


# ---- metric shapes -----------------------------------------------------------------------

def _metric(block, *, as_percent=False, digits=None):
    """{value, valueDiffPercent} -> {value, change_percent} (month over month)."""
    block = _dict(block)
    if not block:
        return None
    if as_percent:
        value = percent(block.get("value"))
    else:
        value = to_float(block.get("value"), digits)
        if value is not None and value.is_integer() and digits is None:
            value = int(value)
    return {"value": value, "change_percent": percent(block.get("valueDiffPercent"))}


def _rank(block):
    """{value, valueDiffStatus, name?, slug?, database?} -> a rank entry.
    `change` is Semrush's month-over-month movement as shown by the site's
    arrows (positive = climbed, negative = dropped, 0 = unchanged)."""
    block = _dict(block)
    if not block:
        return None
    out = {"value": to_int(block.get("value")), "change": to_int(block.get("valueDiffStatus"))}
    if block.get("database") and str(block["database"]).lower() != "global":
        out["country"] = text(block.get("database"))
    if block.get("name") and block.get("slug") and block.get("database") == "global":
        out["category"] = {"slug": text(block.get("slug")), "name": text(block.get("name"))}
    elif block.get("name"):
        out["name"] = text(block.get("name"))
    return out


def _visible(block):
    block = _dict(block)
    return block if block and block.get("visible", True) else None


# ---- /website/<domain>/overview/ ----------------------------------------------------------

def _summary(summary):
    summary = _dict(summary)
    stats = _dict(summary.get("trafficStats"))
    domain = text(summary.get("domain"))
    return {
        "domain": domain,
        "brand_name": text(summary.get("brandName")),
        "link": refs.website_link(domain),
        "favicon": text(summary.get("favicon")),
        "description": text(summary.get("description")),
        "country": text(summary.get("country")),
        "categories": [
            {"slug": text(c.get("slug")), "name": text(c.get("name"))}
            for c in _list(summary.get("categories")) if isinstance(c, dict)
        ],
        "rank": {
            "global": _rank(stats.get("globalRank")),
            "country": _rank(stats.get("countryRank")),
            "category": _rank(stats.get("categoryRank")),
        },
        "authority_score": to_int(_dict(stats.get("authorityScore")).get("value")),
        "visits": to_int(_dict(stats.get("visits")).get("value")),
        "site_health": to_float(_dict(stats.get("siteHealth")).get("value")),
        "data_date": iso_date(summary.get("actualDate")),
        "updated_at": iso_date(summary.get("dateModified")),
    }


def parse_engagement(block):
    block = _visible(block)
    if not block:
        return None
    return {
        "date": iso_date(block.get("displayDate")),
        "visits": _metric(block.get("visits")),
        "pages_per_visit": _metric(block.get("pagesPerVisit"), digits=2),
        "average_visit_duration_seconds": _metric(block.get("timeOnSite")),
        "bounce_rate_percent": _metric(block.get("bounceRate"), as_percent=True),
        "visits_history": [
            {"date": iso_date(h.get("displayDate")), "visits": to_int(h.get("visits"))}
            for h in _list(block.get("visitsHistory")) if isinstance(h, dict)
        ],
    }


def parse_devices(block):
    block = _visible(block)
    if not block:
        return None
    history = [
        {"date": iso_date(h.get("displayDate")), "visits": to_int(h.get("visits")),
         "desktop_visits": to_int(h.get("desktopVisits")), "mobile_visits": to_int(h.get("mobileVisits"))}
        for h in _list(block.get("history")) if isinstance(h, dict)
    ]
    latest = history[0] if history else {}
    total = latest.get("visits") or 0
    return {
        "date": iso_date(block.get("displayDate")),
        "desktop_visits": latest.get("desktop_visits"),
        "mobile_visits": latest.get("mobile_visits"),
        "desktop_share_percent": round(latest["desktop_visits"] * 100 / total, 2) if total and latest.get("desktop_visits") is not None else None,
        "mobile_share_percent": round(latest["mobile_visits"] * 100 / total, 2) if total and latest.get("mobile_visits") is not None else None,
        "history": history,
    }


def parse_traffic_by_country(block):
    block = _visible(block)
    if not block:
        return None
    return {
        "date": iso_date(block.get("displayDate")),
        "countries": [
            {
                "country": text(c.get("country")),
                "name": text(c.get("countryName")),
                "visits": to_int(c.get("traffic")),
                "share_percent": percent(c.get("trafficShare")),
                "desktop_share_percent": percent(c.get("desktopShare")),
                "mobile_share_percent": percent(c.get("mobileShare")),
            }
            for c in _list(block.get("series")) if isinstance(c, dict)
        ],
    }


def _journey_item(item):
    host = text(item.get("host")) or ""
    # "google.com__Google organic" -> source google.com, channel "Google organic";
    # "Direct" -> channel direct; anything else is a referring host.
    source, _, channel = host.partition("__")
    if not channel and source.lower() == "direct":
        source, channel = None, "direct"
    elif not channel:
        channel = "referral"
    else:
        channel = channel.strip().lower()
    return {
        "source": source or None,
        "channel": channel,
        "link": refs.website_link(item.get("slug")) if item.get("slug") else None,
        "share_percent": percent(item.get("share")),
        "visits": to_int(item.get("value")),
        "previous_visits": to_int(item.get("prevValue")),
    }


def parse_traffic_sources(block):
    block = _visible(block)
    if not block:
        return None
    incoming = _dict(block.get("in"))
    outgoing = _dict(block.get("out"))
    return {
        "date": iso_date(block.get("displayDate") or block.get("display_date")),
        "incoming": [_journey_item(i) for i in _list(incoming.get("items")) if isinstance(i, dict)],
        "outgoing": [
            {
                "domain": text(i.get("host")),
                "link": refs.website_link(i.get("slug")) if i.get("slug") else None,
                "share_percent": percent(i.get("share")),
                "visits": to_int(i.get("value")),
                "previous_visits": to_int(i.get("prevValue")),
            }
            for i in _list(outgoing.get("items")) if isinstance(i, dict)
        ],
    }


def parse_ai_traffic(block):
    block = _dict(block)
    if not block or not block.get("items"):
        return None
    other = _dict(_dict(block.get("other")).get("traffic"))
    return {
        "platforms": [
            {
                "domain": text(i.get("id")),
                "name": text(i.get("name")) or text(i.get("id")),
                "visits": to_int(_dict(i.get("traffic")).get("value")),
                "share_percent": percent(_dict(i.get("traffic")).get("share")),
                "history": [
                    {"date": iso_date(h.get("date")), "visits": to_int(h.get("value"))}
                    for h in _list(_dict(i.get("traffic")).get("history")) if isinstance(h, dict)
                ],
            }
            for i in _list(block.get("items")) if isinstance(i, dict)
        ],
        "other_visits": to_int(other.get("value")),
        "other_share_percent": percent(other.get("share")),
    }


def parse_search_traffic(block):
    block = _visible(block)
    if not block:
        return None
    return {
        "date": iso_date(block.get("displayDate")),
        "organic": _metric(block.get("organic")),
        "paid": _metric(block.get("paid")),
        "history": [
            {"date": iso_date(h.get("displayDate")), "organic": to_int(h.get("organic")),
             "paid": to_int(h.get("paid")), "total": to_int(h.get("total"))}
            for h in _list(block.get("history")) if isinstance(h, dict)
        ],
    }


def _intents(value):
    codes = [c for c in re.split(r"[^0-9]+", str(value or "")) if c]
    return [INTENTS.get(c, c) for c in codes]


def parse_top_keywords(block):
    block = _visible(block)
    if not block:
        return None
    return {
        "date": iso_date(block.get("displayDate")),
        "country": text(block.get("country")),
        "keywords": [
            {
                "keyword": text(k.get("keyword")),
                "position": to_int(k.get("position")),
                "search_volume": to_int(k.get("searchVolume")),
                "cpc": to_float(k.get("cpc")),
                "currency": "USD",
                "intents": _intents(k.get("intents")),
                "traffic_share_percent": percent(k.get("traffic")),
            }
            for k in _list(block.get("series")) if isinstance(k, dict)
        ],
    }


def parse_backlinks(block):
    block = _visible(block)
    if not block:
        return None
    return {
        "date": iso_date(block.get("displayDate")),
        "authority_score": to_int(_dict(block.get("authorityScore")).get("value")),
        "backlinks": _metric(block.get("backlinks")),
        "referring_domains": _metric(block.get("referringDomains")),
        "google_penalty_risk": (text(_dict(block.get("googlePenaltyRisk")).get("value")) or "").lower() or None,
        "backlinks_history": [
            {"date": iso_date(h.get("displayDate")), "backlinks": to_int(h.get("backlinks"))}
            for h in _list(block.get("backlinksHistory")) if isinstance(h, dict)
        ],
        "referring_domains_history": [
            {"date": iso_date(h.get("displayDate")), "referring_domains": to_int(h.get("referringDomains"))}
            for h in _list(block.get("referringDomainsHistory")) if isinstance(h, dict)
        ],
    }


def parse_overview_competitors(block):
    block = _visible(block)
    if not block:
        return None
    return {
        "date": iso_date(block.get("displayDate")),
        "competitors": [
            {
                "domain": text(c.get("slug")) or text(c.get("name")),
                "link": refs.website_link(text(c.get("slug")) or text(c.get("name"))),
                "favicon": text(c.get("favicon")),
                "relevance_percent": percent(c.get("relevance")),
                "visits": to_int(c.get("visits")),
            }
            for c in _list(block.get("items")) if isinstance(c, dict)
        ],
    }


def parse_site_audit(block):
    block = _dict(block)
    if not block or not block.get("visible"):
        return None
    top = _dict(block.get("onTop"))
    health = _dict(block.get("siteHealth"))
    crawled = _dict(block.get("crawledPages"))
    thematic = _dict(block.get("thematicReports"))
    return {
        "date": iso_date(block.get("displayDate")),
        "site_health_percent": to_float(health.get("health")),
        "site_health_change": to_float(health.get("healthDelta")),
        "errors_count": to_int(top.get("errors")),
        "warnings_count": to_int(top.get("warnings")),
        "notices_count": to_int(top.get("notices")),
        "pages": {
            "crawled": to_int(crawled.get("pagesCrawled")),
            "healthy": to_int(crawled.get("healthyPages")),
            "broken": to_int(crawled.get("brokenPages")),
            "with_issues": to_int(crawled.get("haveIssuesPages")),
            "redirects": to_int(crawled.get("redirectPages")),
            "blocked": to_int(crawled.get("blockedPages")),
        },
        "thematic_scores": {
            key: to_float(thematic.get(raw))
            for key, raw in (("https", "https"), ("international", "international"), ("crawlability", "crawlability"),
                             ("performance", "performance"), ("internal_linking", "linking"), ("markup", "markups"),
                             ("core_web_vitals", "webVitals"))
        },
    }


def _related(summary):
    summary = _dict(summary)
    out = {}
    for key, raw in (("previous", "prevRelatedLink"), ("next", "nextRelatedLink")):
        item = _dict(summary.get(raw))
        slug = text(item.get("slug"))
        out[key] = {"domain": slug, "link": refs.website_link(slug)} if slug else None
    return out


def parse_overview(props):
    """The whole /website/<domain>/overview/ dataset."""
    page = _dict(_dict(props).get("page"))
    data = _dict(page.get("data"))
    summary = _summary(data.get("summary"))
    summary.update({
        "traffic": parse_engagement(data.get("visitorEngagement")),
        "traffic_by_device": parse_devices(data.get("trafficByDevice")),
        "traffic_by_country": parse_traffic_by_country(data.get("trafficByCountry")),
        "traffic_sources": parse_traffic_sources(data.get("trafficJourney")),
        "ai_traffic": parse_ai_traffic(data.get("trafficAi")),
        "search_traffic": parse_search_traffic(data.get("searchTraffic")),
        "top_keywords": parse_top_keywords(data.get("keywords")),
        "backlinks": parse_backlinks(data.get("backlinks")),
        "competitors": parse_overview_competitors(data.get("competitors")),
        "site_audit": parse_site_audit(data.get("siteAudit")),
        "related_domains": _related(data.get("summary")),
    })
    return summary


# ---- /website/<domain>/competitors/ -------------------------------------------------------

def _competitor_profile(item):
    item = _dict(item)
    domain = text(item.get("domain"))
    return {
        "domain": domain,
        "brand_name": text(item.get("brandName")),
        "link": refs.website_link(domain),
        "favicon": text(item.get("favicon")),
        "description": text(item.get("description")),
        "country": text(item.get("country")),
        "rank": {
            "global": _rank(item.get("globalRank")),
            "country": _rank(item.get("countryRank")),
            "category": _rank(item.get("categoryRank")),
        },
        "authority_score": to_int(_dict(item.get("authorityScore")).get("value")),
        "visits": _metric(item.get("visits")),
        "pages_per_visit": _metric(item.get("pagesPerVisit"), digits=2),
        "average_visit_duration_seconds": _metric(item.get("timeOnSite")),
        "bounce_rate_percent": _metric(item.get("bounceRate"), as_percent=True),
        "data_date": iso_date(item.get("actualDate")),
        "updated_at": iso_date(item.get("dateModified")),
    }


def parse_competitors(props):
    page = _dict(_dict(props).get("page"))
    site = _competitor_profile(page.get("summary"))
    competitors = [_competitor_profile(c) for c in _list(page.get("competitors")) if isinstance(c, dict)]
    visits = [c["visits"]["value"] for c in competitors if c.get("visits") and c["visits"].get("value")]
    own = (site.get("visits") or {}).get("value") or 0
    market = own + sum(visits)
    for c in competitors:
        value = (c.get("visits") or {}).get("value")
        c["market_share_percent"] = round(value * 100 / market, 2) if market and value else None
    site["market_share_percent"] = round(own * 100 / market, 2) if market and own else None
    site["competitors"] = competitors
    return site


# ---- /trending-websites/<country>/<category> ----------------------------------------------

def _trending_names(state):
    """slug -> display name from the page's i18n bundle (the message id is
    the slug itself for countries and categories)."""
    messages = _dict(_dict(state.get("i18n")).get("messages"))
    out = {}
    for key, value in messages.items():
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
            out[key] = value[0]
        elif isinstance(value, str):
            out[key] = value
    return out


def parse_trending(state, country, category):
    state = _dict(state)
    data = _dict(state.get("data"))
    names = _trending_names(state)
    domains = []
    for index, d in enumerate(_list(data.get("domains")), start=1):
        if not isinstance(d, dict):
            continue
        domain = text(d.get("domain_name"))
        domains.append({
            "rank": index,
            "domain": domain,
            "link": refs.website_link(domain),
            "visits": to_int(d.get("total_traffic")),
            "desktop_visits": to_int(d.get("desktop_traffic")),
            "desktop_share_percent": to_float(d.get("desktop_percent"), 2),
            "mobile_visits": to_int(d.get("mobile_traffic")),
            "mobile_share_percent": to_float(d.get("mobile_percent"), 2),
            "month_over_month_percent": to_float(d.get("mom"), 2),
            "year_over_year_percent": to_float(d.get("yoy"), 2),
            "top_source": text(d.get("top_source")),
        })
    cat = _dict(state.get("category"))
    return {
        "country": country,
        "country_name": names.get(country) or ("Worldwide" if country == "global" else None),
        "category": {
            "slug": text(cat.get("name")) or category,
            "name": names.get(text(cat.get("name")) or category) or ("All categories" if category == "all" else None),
        },
        "link": refs.trending_link(country, category),
        "date": iso_date(data.get("date") or state.get("date")),
        "market": {
            "visits": to_int(data.get("totaltraffic")),
            "change_percent": to_float(data.get("totaltraffic_change"), 2),
            "history": [
                {"date": iso_date(h.get("date")), "visits": to_int(h.get("traffic"))}
                for h in _list(data.get("traffic")) if isinstance(h, dict)
            ],
        },
        "count": len(domains),
        "websites": domains,
    }


def parse_trending_categories(state):
    state = _dict(state)
    names = _trending_names(state)
    return [{"slug": slug, "name": names.get(slug), "link": refs.trending_link("global", slug)}
            for slug in _list(state.get("categories")) if isinstance(slug, str)]


def parse_trending_countries(state):
    state = _dict(state)
    names = _trending_names(state)
    return [{"country": code.lower(), "name": names.get(code), "link": refs.trending_link(code, "all")}
            for code in _list(state.get("countries")) if isinstance(code, str)]


# ---- /popular/<slug>/ ---------------------------------------------------------------------

def parse_popular(props, slug):
    page = _dict(_dict(props).get("page"))
    data = _dict(page.get("data"))
    items = [
        {
            "rank": to_int(i.get("rank")),
            "keyword": text(i.get("name")),
            "search_volume": to_int(i.get("volume")),
            "keyword_difficulty": to_int(i.get("kd")),
            "cpc": to_float(i.get("cpc")),
            "currency": "USD",
        }
        for i in _list(data.get("items")) if isinstance(i, dict)
    ]
    return {
        "category": text(page.get("slug")) or slug,
        "name": text(data.get("categoryPlural")),
        "title": text(page.get("title")),
        "link": refs.popular_link(text(page.get("slug")) or slug),
        "date": iso_date(data.get("date")),
        "next_refresh_date": iso_date(data.get("nextRefreshDate")),
        "total_searches": to_int(data.get("totalSearches")),
        "count": to_int(data.get("totalItems")) or len(items),
        "keywords": items,
    }


# ---- /search-bar/api/search/suggestions ---------------------------------------------------

def parse_suggestions(body, kind):
    out = []
    for item in _list(_dict(body).get("suggestions")):
        message = _dict(_dict(item).get("message"))
        value = text(message.get("text"))
        if not value:
            continue
        if kind == "domains":
            out.append({"domain": value, "link": refs.website_link(value)})
        else:
            out.append({"keyword": value})
    return out
