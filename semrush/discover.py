"""/semrush/top-websites, /semrush/popular, /semrush/autocomplete — the
public ranking lists and the search-bar suggestions (plain curl_cffi)."""
from semrush import parsers as P
from semrush import refs
from semrush.fetch import SemrushNotFound, SemrushUpstreamError, dump_debug, get_html, get_json

_SUGGEST_TYPE = {"domains": 1, "keywords": 2}


def _trending_state(country, category):
    link = refs.trending_link(country, category)
    html = get_html(link, label=f"trending-websites/{country}/{category}",
                    missing=f"semrush has no top-websites list for country '{country}' / category '{category}'")
    state = P.preloaded_state(html)
    if not state or not isinstance(state.get("data"), dict):
        dump_debug("trending", html)
        raise SemrushUpstreamError("trending-websites page carries no state")
    return state


def top_websites(country, category):
    state = _trending_state(country, category)
    if not (state.get("data") or {}).get("domains"):
        raise SemrushNotFound(f"semrush has no top-websites list for country '{country}' / category '{category}'")
    return P.parse_trending(state, country, category)


def top_website_categories():
    state = _trending_state("global", "all")
    items = P.parse_trending_categories(state)
    return {"count": len(items), "categories": items}


def top_website_countries():
    state = _trending_state("global", "all")
    items = P.parse_trending_countries(state)
    return {"count": len(items), "countries": items}


def popular(category):
    html = get_html(refs.popular_link(category), label=f"popular/{category}",
                    missing=f"semrush has no popular list '{category}'")
    props = P.astro_props(html, "PopularView")
    if not props:
        dump_debug("popular", html)
        raise SemrushUpstreamError("popular page carries no data island")
    return P.parse_popular(props, category)


def autocomplete(query, type):
    body = get_json("/search-bar/api/search/suggestions", {"q": query, "type": _SUGGEST_TYPE[type]},
                    label="search-bar/suggestions")
    items = P.parse_suggestions(body, type)
    return {"query": query, "type": type, "count": len(items), "suggestions": items}
