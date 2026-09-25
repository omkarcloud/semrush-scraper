"""Offline tests: ref parsing, the request schemas and the normalizers
against raw Semrush payloads captured 2026-09-25 (semrush/fixtures/*.json:
decoded astro-island props of the public pages, the trending page's
__PRELOADED_STATE__, and the free-tools API `data` objects).

    python -m pytest semrush/test_parsers.py -q
"""
import json
import os

import pytest

from schema_fields import load_query
from semrush import parsers as P
from semrush import refs
from semrush import schemas
from semrush import tool_parsers as TP

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def fx(name):
    with open(os.path.join(FIX, name + ".json")) as f:
        return json.load(f)


def tool_fx(name):
    return fx(name)["data"]


def _clean_keys(obj, path="$"):
    """Every emitted key is snake_case, no key is named *url* / camelCase,
    and no value is "" or "N/A"."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            assert key == key.lower() and " " not in key and "-" not in key, f"{path}.{key} not snake_case"
            assert "url" not in key, f"{path}.{key} should be a *link"
            assert key != "__typename"
            _clean_keys(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            _clean_keys(value, f"{path}[{i}]")
    elif isinstance(obj, str):
        assert obj not in ("", "N/A"), f"{path} is an empty placeholder"


# ---- refs -----------------------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [
    ("amazon.com", "amazon.com"), ("WWW.Amazon.com", "amazon.com"), ("https://www.amazon.com/dp/B0?x=1", "amazon.com"),
    ("amazon.co.uk/gp/help", "amazon.co.uk"), ("https://www.semrush.com/website/amazon.com/overview/", "amazon.com"),
    ("https://de.semrush.com/website/ebay.com/competitors/", "ebay.com"), ("support.google.com", "support.google.com"),
])
def test_resolve_domain(value, expected):
    assert refs.resolve_domain(value) == expected


@pytest.mark.parametrize("value", ["", "amazon", "not a domain", "https://www.semrush.com/analytics/overview/?q=x"])
def test_resolve_domain_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_domain(value)


def test_resolve_domains_and_hint():
    assert refs.resolve_domains("amazon.com, https://ebay.com/x ,AMAZON.com") == ["amazon.com", "ebay.com"]
    with pytest.raises(ValueError):
        refs.resolve_domains(",".join(f"d{i}.com" for i in range(11)))
    assert refs.root_domain_hint("support.google.com") == "google.com"
    assert refs.root_domain_hint("news.bbc.co.uk") == "bbc.co.uk"
    assert refs.root_domain_hint("amazon.co.uk") is None
    assert refs.root_domain_hint("amazon.com") is None


@pytest.mark.parametrize("value, expected", [
    ("", "global"), ("Global", "global"), ("US", "us"), ("gb", "gb"),
])
def test_resolve_country(value, expected):
    assert refs.resolve_country(value) == expected


@pytest.mark.parametrize("value, expected", [
    ("", "all"), ("All", "all"), ("online-services", "online-services"), ("Online Services", "online-services"),
    ("Accounting & Auditing", "accounting-and-auditing"), ("TV and Movies", "tv-and-movies"),
])
def test_resolve_category(value, expected):
    assert refs.resolve_category(value) == expected


@pytest.mark.parametrize("value, expected", [
    ("books", "books"), ("Book", "books"), ("https://www.semrush.com/popular/beer-brands/", "beer-brands"),
    ("board games", "board-games"),
])
def test_resolve_popular(value, expected):
    assert refs.resolve_popular(value) == expected


def test_resolve_popular_rejects():
    with pytest.raises(ValueError):
        refs.resolve_popular("cars")


# ---- schemas --------------------------------------------------------------------------

def test_schemas():
    data, err = load_query(schemas.DomainSchema, {"domain": "https://www.amazon.com/"})
    assert err is None and data == {"domain": "amazon.com"}
    _, err = load_query(schemas.DomainSchema, {"domain": "amazon.com", "device": "mobile"})
    assert err and "device" in err["errors"]
    data, _ = load_query(schemas.TopWebsitesSchema, {})
    assert data == {"country": "global", "category": "all"}
    data, _ = load_query(schemas.TopWebsitesSchema, {"country": "US", "category": "Finance"})
    assert data == {"country": "us", "category": "finance"}
    data, _ = load_query(schemas.KeywordSchema, {"keyword": "  seo   tools "})
    assert data == {"keyword": "seo tools", "country": "US"}
    _, err = load_query(schemas.KeywordSchema, {"keyword": "x", "country": "usa"})
    assert err and "country" in err["errors"]
    data, _ = load_query(schemas.AutocompleteSchema, {"query": "ama", "type": "Domains"})
    assert data == {"query": "ama", "type": "domains"}
    data, _ = load_query(schemas.KeywordRankSchema, {"domain": "semrush.com", "keyword": "seo tools", "country": "gb"})
    assert data == {"domain": "semrush.com", "keyword": "seo tools", "country": "GB"}
    _, err = load_query(schemas.UrlSchema, {"url": "mailchimp.com"})
    assert err
    data, _ = load_query(schemas.UrlSchema, {"url": "https://mailchimp.com/"})
    assert data == {"url": "https://mailchimp.com/"}


# ---- public pages ---------------------------------------------------------------------

def test_astro_decoder():
    raw = '<astro-island uid="x" component-export="WebsiteView" props="{&quot;page&quot;:[0,{&quot;data&quot;:[0,{&quot;items&quot;:[1,[[0,1],[0,2]]]}]}]}"></astro-island>'
    assert P.astro_props(raw, "WebsiteView") == {"page": {"data": {"items": [1, 2]}}}
    assert P.astro_props(raw, "Other") is None
    assert P.astro_props("<html></html>") is None
    state = P.preloaded_state('<script>window.__PRELOADED_STATE__ = {"a": 1};</script>')
    assert state == {"a": 1}


def test_overview():
    out = P.parse_overview(fx("website_overview_props"))
    _clean_keys(out)
    assert out["domain"] == "amazon.com" and out["link"] == "https://www.semrush.com/website/amazon.com/overview/"
    assert out["rank"]["global"] == {"value": 13, "change": -1}
    assert out["rank"]["country"]["country"] == "US" and out["rank"]["country"]["value"] == 5
    assert out["rank"]["category"]["category"]["slug"] == "online-services"
    assert out["authority_score"] == 100 and out["visits"] == 2329167591
    assert out["traffic"]["bounce_rate_percent"]["value"] == 41.12
    assert out["traffic"]["average_visit_duration_seconds"]["value"] == 694
    assert len(out["traffic"]["visits_history"]) == 3
    assert out["traffic_by_device"]["desktop_share_percent"] + out["traffic_by_device"]["mobile_share_percent"] == 100
    assert len(out["traffic_by_device"]["history"]) == 6
    assert out["traffic_by_country"]["countries"][0]["country"] == "US"
    assert out["traffic_by_country"]["countries"][0]["share_percent"] == 80.58
    sources = out["traffic_sources"]["incoming"]
    assert sources[0]["channel"] == "direct" and sources[0]["source"] is None
    assert sources[1] == {"source": "google.com", "channel": "google organic", "link": None,
                          "share_percent": 15.8, "visits": 165937446, "previous_visits": 168838785}
    assert out["traffic_sources"]["outgoing"][0]["domain"] == "google.com"
    assert out["ai_traffic"]["platforms"][0]["name"] == "ChatGPT" and len(out["ai_traffic"]["platforms"][0]["history"]) == 6
    assert out["ai_traffic"]["platforms"][1]["name"] == "markable.ai"
    assert out["search_traffic"]["organic"]["value"] == 636824989 and out["search_traffic"]["history"][0]["total"] == 656703640
    kw = out["top_keywords"]["keywords"][0]
    assert kw["keyword"] == "amazon" and kw["intents"] == ["navigational"] and kw["traffic_share_percent"] == 23.78
    assert out["top_keywords"]["keywords"][3]["intents"] == ["commercial"]
    assert out["backlinks"]["backlinks"]["value"] == 5844906372 and out["backlinks"]["google_penalty_risk"] == "low"
    assert len(out["backlinks"]["referring_domains_history"]) == 6
    assert out["competitors"]["competitors"][0] == {
        "domain": "ebay.com", "link": "https://www.semrush.com/website/ebay.com/overview/",
        "favicon": "https://static.semrush.com/power-pages/media/favicons/ebay-com-favicon-67c7209c.png",
        "relevance_percent": 52.0, "visits": 532364377}
    assert out["site_audit"] is None
    assert out["related_domains"]["next"]["domain"] == "amazon.com.au"
    assert out["data_date"] == "2026-08-15" and out["updated_at"] == "2026-09-17"


def test_overview_partial():
    out = P.parse_overview({"page": {"data": {"summary": {"domain": "x.com"}}}})
    assert out["domain"] == "x.com" and out["traffic"] is None and out["backlinks"] is None
    assert P.parse_overview({}) ["domain"] is None


def test_competitors():
    out = P.parse_competitors(fx("website_competitors_props"))
    _clean_keys(out)
    assert out["domain"] == "amazon.com" and out["description"].startswith("Free delivery")
    assert len(out["competitors"]) == 7
    first = out["competitors"][0]
    assert first["domain"] == "ebay.com" and first["rank"]["global"] == {"value": 64, "change": -4}
    assert first["visits"] == {"value": 532364377, "change_percent": -4.38}
    assert first["bounce_rate_percent"]["value"] == 44.32
    assert 0 < first["market_share_percent"] < 100 and out["market_share_percent"] > first["market_share_percent"]


def test_trending():
    state = fx("trending_state")
    out = P.parse_trending(state, "us", "finance")
    _clean_keys(out)
    assert out["country_name"] == "United States" and out["category"] == {"slug": "finance", "name": "Finance"}
    assert out["count"] == 99 and out["websites"][0]["rank"] == 1 and out["websites"][0]["domain"] == "yahoo.com"
    assert out["websites"][0]["month_over_month_percent"] == -7.98 and out["websites"][0]["top_source"] == "direct"
    assert len(out["market"]["history"]) == 12 and out["market"]["visits"] == 3711102258
    cats = P.parse_trending_categories(state)
    assert len(cats) == 111 and cats[0]["name"] == "Accounting & Auditing"
    countries = P.parse_trending_countries(state)
    assert len(countries) == 240 and countries[0] == {"country": "ad", "name": "Andorra",
                                                       "link": "https://www.semrush.com/trending-websites/ad/all"}


def test_popular():
    out = P.parse_popular(fx("popular_props"), "books")
    _clean_keys(out)
    assert out["category"] == "books" and out["count"] == 440 and out["date"] == "2026-03-19"
    assert out["keywords"][0] == {"rank": 1, "keyword": "allegiant", "search_volume": 1000000,
                                  "keyword_difficulty": 88, "cpc": 0.22, "currency": "USD"}


def test_suggestions():
    body = {"suggestions": [{"message": {"text": "amazon.com", "type": 1}}, {"message": {"text": "", "type": 1}}]}
    assert P.parse_suggestions(body, "domains") == [{"domain": "amazon.com", "link": "https://www.semrush.com/website/amazon.com/overview/"}]
    assert P.parse_suggestions({"suggestions": [{"message": {"text": "email marketing"}}]}, "keywords") == [{"keyword": "email marketing"}]
    assert P.parse_suggestions({}, "keywords") == []


# ---- free-tools -------------------------------------------------------------------------

def test_keyword_overview():
    out = TP.parse_keyword_overview(tool_fx("keyword-checker"), "seo tools", "US")
    _clean_keys(out)
    assert out["keyword"] == "seo tools" and out["country"] == "US"
    assert out["search_volume"] == 550000 and out["keyword_difficulty"] == 95 and out["cpc"] == 7.79
    assert out["intents"] == ["informational", "commercial"] and out["has_ai_overview"] is True
    assert out["global_volume"][0] == {"country": "us", "search_volume": 550000}
    groups = {g["feature"]: g for g in out["serp"]}
    assert groups["organic"]["feature_code"] == -1 and groups["organic"]["count"] == 10
    assert groups["ai overview"]["feature_code"] == 52
    row = groups["organic"]["results"][0]
    assert row["domain"] == "smallseotools.com" and row["authority_score"] == 74
    assert row["serp_features"][0] == {"code": 6, "name": "sitelinks"}
    assert out["related_keywords"][0]["keyword"] == "and seo tools" and out["related_keywords"][0]["intents"] == ["informational"]


def test_keyword_volume_same_shape():
    out = TP.parse_keyword_overview(tool_fx("keyword-search-volume-checker"), "seo tools", "US")
    _clean_keys(out)
    assert out["search_volume"] == 550000 and out["results_count"] is None and out["serp"]


def test_keyword_ideas():
    out = TP.parse_keyword_ideas(tool_fx("keyword-tool"), "seo tools", "US")
    _clean_keys(out)
    assert out["count"] == 25 and out["related_keywords_count"] == 10000 and out["is_related_count_capped"] is True
    assert out["keywords"][0]["keyword"] == "seo tools" and out["keywords"][0]["intents"] == ["informational", "commercial"]


def test_serp():
    out = TP.parse_serp(tool_fx("serp-checker"), "seo tools", "US")
    _clean_keys(out)
    assert out["results_count"] == 122 and len(out["volatility"]) == 30
    assert out["volatility"][0] == {"date": "2026-09-25", "score": 9.4}
    assert out["serp"][0]["feature"] == "organic" and out["serp"][0]["results"][0]["position"] == 1


def test_keyword_rank():
    out = TP.parse_keyword_rank(tool_fx("keyword-rank-checker"), "semrush.com", "seo tools", "US")
    _clean_keys(out)
    assert out["is_ranking"] is True and out["position"] == 7 and out["link"] == "https://www.semrush.com/seo/"
    assert out["keyword_overview"] == {"search_volume": 550000, "keyword_difficulty": 95, "cpc": 7.79, "currency": "USD"}
    assert out["domain_keywords"][0]["keyword"] == "keyword research" and out["domain_keywords"][0]["traffic_share_percent"] == 12.86
    assert out["serp"][0]["feature"] == "organic"


def test_backlinks_report():
    out = TP.parse_backlinks_report(tool_fx("backlink-checker"), "mailchimp.com")
    _clean_keys(out)
    assert out["authority_score"] == 76 and out["backlinks_count"] == 65773393 and out["dofollow_percent"] == 95.44
    assert out["count"] == 25
    assert out["backlinks"][0]["source_link"] == "https://www.covalentlogic.com/" and out["backlinks"][0]["anchor"] is None
    assert out["backlinks"][0]["is_nofollow"] is False and out["backlinks"][0]["page_score"] == 93


def test_authority():
    out = TP.parse_authority(tool_fx("website-authority-checker"), "mailchimp.com")
    _clean_keys(out)
    assert out["authority_score"] == {"value": 76, "change_percent": -1.3}
    assert out["organic_traffic"]["value"] == 22269
    assert len(out["authority_score_history"]) == 13 and out["score_breakdown"]["health"] == "very good"
    assert out["top_competitors"][0]["domain"] == "salesforce.com"
    assert out["top_pages_by_backlinks"][0]["backlinks_count"] == 40471088


def test_competitor_finder():
    out = TP.parse_competitor_finder(tool_fx("competitor-finder"), "mailchimp.com", "US")
    _clean_keys(out)
    assert out["count"] == 10 and out["competitors"][0] == {
        "domain": "hubspot.com", "relevance_percent": 10.0, "common_keywords_count": 14879,
        "organic_keywords_count": 735142, "organic_traffic": 2946812}


def test_ai_traffic_report():
    out = TP.parse_ai_traffic_report(tool_fx("ai-traffic-checker"), "mailchimp.com")
    _clean_keys(out)
    assert out["ai_traffic"] == 12030 and out["top_platform"] == "chatgpt" and out["platforms"][0]["share_percent"] == 69.56
    assert len(out["ai_traffic_history"]) == 6 and out["ai_overviews"]["positions_count"] == 14158
    assert out["traffic_by_channel"][0]["channel"] == "organic_search"
    assert out["top_pages"][0]["ai_visits"] == 2341 and out["ai_search_visibility"][0]["mentions_count"] == 3547


def test_ai_visibility():
    out = TP.parse_ai_visibility(tool_fx("ai-visibility-checker"), "mailchimp.com")
    _clean_keys(out)
    assert out["visibility_score"] == 70 and out["mentions_count"] == 16054 and out["citations_count"] == 7014
    assert out["visibility_score_trend"][0] == {"month": "2026-06", "visibility_score": 74}
    assert out["mentions_by_engine"][0] == {"engine": "chatgpt", "name": "ChatGPT", "value": 3547}
    assert out["best_topics"][0]["topic"] == "Email Marketing Platforms and Services"
    assert out["top_cited_pages"][0]["link"] == "https://mailchimp.com"


def test_seo_audit():
    out = TP.parse_seo_audit(tool_fx("seo-checker"), "https://mailchimp.com/")
    _clean_keys(out)
    assert out["scores"] == {"total": 77, "on_page_seo": 55, "off_page_seo": 75, "technical_seo": 80, "social_media": 100}
    assert out["status"] == "partial" and len(out["issues"]) == 5
    assert out["on_page_seo"]["title"]["status"] == "warning" and out["on_page_seo"]["title"]["length"] == 42
    assert out["on_page_seo"]["title"]["value"] == "Email & SMS Marketing Platform | Mailchimp"
    assert "&amp;" not in out["on_page_seo"]["images"]["missing_alt"][0]
    assert out["on_page_seo"]["h1"]["status"] == "fail"
    assert out["on_page_seo"]["content"]["words_count"] == 5248
    assert out["on_page_seo"]["heading_structure"]["counts"]["h2"] == 11
    assert out["on_page_seo"]["page_link"]["length"] == 13
    assert out["on_page_seo"]["keyword_density"]["groups"][0]["phrases"][0]["phrase"] == "free"
    assert out["technical_seo"]["robots_txt"]["status"] == "fail" and out["technical_seo"]["robots_txt"]["rules"][0]["type"] == "sitemap"
    assert out["technical_seo"]["hreflang"]["value"][0]["hreflang"] == "x-default"
    assert out["off_page_seo"]["authority_score"] == {"status": "pass", "value": 89, "competitor_average": 72,
                                                      "messages": out["off_page_seo"]["authority_score"]["messages"]}
    assert out["social_media"]["twitter"]["value"] == "https://x.com/Mailchimp"
    assert out["top_keywords"][0]["keyword"] == "mailchimp" and out["top_pages"][0]["keywords_count"] == 3453
    assert out["competitors"][0]["relevance_percent"] == 10.0 and out["top_backlinks"][0]["page_score"] == 93


def test_tool_parsers_never_crash_on_empty():
    assert TP.parse_keyword_overview({}, "k", "US")["keyword"] == "k"
    assert TP.parse_keyword_ideas(None, "k", "US")["count"] == 0
    assert TP.parse_serp({}, "k", "US")["serp"] == []
    assert TP.parse_keyword_rank({}, "d", "k", "US")["is_ranking"] is False
    assert TP.parse_backlinks_report({}, "d")["count"] == 0
    assert TP.parse_authority({}, "d")["score_breakdown"] is None
    assert TP.parse_competitor_finder({}, "d", "US")["competitors"] == []
    assert TP.parse_ai_traffic_report({}, "d")["ai_overviews"] is None
    assert TP.parse_ai_visibility({}, "d")["competitors"] == []
    assert TP.parse_seo_audit({}, "https://x.com/")["scores"]["total"] is None
