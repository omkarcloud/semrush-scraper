"""Live endpoint smoke tests: one call per /semrush/* route against a running
service, with example values proven to return data (2026-09-25). The
listing tooling reads each route's FIRST call from this file's AST as its
working example, so the values stay literals.

Skipped unless SEMRUSH_BASE points at a running service:

    ONLY_SCRAPER=semrush python run.py
    SEMRUSH_BASE=http://127.0.0.1:6002 python -m pytest semrush/test_endpoints.py -q

The free-tools routes (keywords/*, domains/backlinks|authority|
competitor-finder|ai-traffic-report|ai-visibility, pages/seo-audit) launch
the headed captcha browser on first use and spend one residential exit's
daily attempt each; SEMRUSH_SKIP_TOOLS=1 leaves them out.
"""
import os

import pytest

BASE = os.environ.get("SEMRUSH_BASE", "").rstrip("/")
SKIP_TOOLS = os.environ.get("SEMRUSH_SKIP_TOOLS") == "1"

pytestmark = pytest.mark.skipif(not BASE, reason="set SEMRUSH_BASE to run live endpoint tests")
tools = pytest.mark.skipif(SKIP_TOOLS, reason="SEMRUSH_SKIP_TOOLS=1")


def call(path, status=200, **params):
    from curl_cffi import requests
    resp = requests.get(BASE + path, params=params, timeout=300)
    assert resp.status_code == status, f"{path} {params} -> {resp.status_code} {resp.text[:300]}"
    body = resp.json()
    assert body, f"{path} returned an empty body"
    return body


def test_domain_overview():
    out = call("/semrush/domains/overview", domain="amazon.com")
    assert out["domain"] == "amazon.com" and out["authority_score"] >= 90 and out["visits"] > 1_000_000_000
    assert out["rank"]["global"]["value"] < 100 and out["traffic"]["visits_history"] and out["backlinks"]["backlinks"]["value"]
    assert out["traffic_sources"]["incoming"] and out["ai_traffic"]["platforms"] and out["top_keywords"]["keywords"]
    assert call("/semrush/domains/overview", domain="https://www.amazon.com/dp/B08N5WRWNW")["domain"] == "amazon.com"
    assert call("/semrush/domains/overview", domain="https://www.semrush.com/website/ebay.com/competitors/")["domain"] == "ebay.com"
    call("/semrush/domains/overview", status=404, domain="support.google.com")
    call("/semrush/domains/overview", status=404, domain="zzzz-no-such-domain-9999.com")
    call("/semrush/domains/overview", status=400, domain="not a domain")


def test_domain_slices():
    assert call("/semrush/domains/rank", domain="github.com")["rank"]["global"]["value"]
    traffic = call("/semrush/domains/traffic", domain="github.com")
    assert traffic["traffic"]["visits"]["value"] and len(traffic["traffic_by_device"]["history"]) == 6
    assert call("/semrush/domains/traffic-by-country", domain="github.com")["countries"][0]["share_percent"]
    sources = call("/semrush/domains/traffic-sources", domain="github.com")
    assert sources["incoming"] and sources["outgoing"]
    assert call("/semrush/domains/ai-traffic", domain="github.com")["platforms"]
    assert call("/semrush/domains/search-traffic", domain="github.com")["search_traffic"]["organic"]["value"]
    assert call("/semrush/domains/top-keywords", domain="github.com")["keywords"][0]["search_volume"]
    assert call("/semrush/domains/backlinks-overview", domain="github.com")["backlinks"]["referring_domains"]["value"]
    competitors = call("/semrush/domains/competitors", domain="github.com")
    assert len(competitors["competitors"]) >= 5 and competitors["competitors"][0]["rank"]["global"]["value"]
    assert "related_domains" in call("/semrush/domains/related", domain="amazon.com")
    batch = call("/semrush/domains/batch", domains="amazon.com,github.com,zzzz-no-such-domain-9999.com")
    assert batch["count"] == 3 and batch["domains"][0]["authority_score"] and batch["domains"][2]["error"]


def test_top_websites():
    out = call("/semrush/top-websites")
    assert out["country"] == "global" and out["count"] >= 90 and out["websites"][0]["domain"] and out["market"]["history"]
    us = call("/semrush/top-websites", country="us", category="finance")
    assert us["category"]["name"] == "Finance" and us["websites"][0]["visits"]
    call("/semrush/top-websites", status=404, country="us", category="no-such-category")
    assert call("/semrush/top-websites/categories")["count"] > 100
    assert call("/semrush/top-websites/countries")["count"] > 200


def test_popular_and_autocomplete():
    out = call("/semrush/popular", category="books")
    assert out["count"] > 300 and out["keywords"][0]["search_volume"]
    call("/semrush/popular", status=400, category="cars")
    assert call("/semrush/keywords/autocomplete", query="email mark")["suggestions"][0]["keyword"]
    assert call("/semrush/keywords/autocomplete", query="amaz", type="domains")["suggestions"][0]["domain"]


@tools
def test_keyword_tools():
    out = call("/semrush/keywords/overview", keyword="email marketing", country="US")
    assert out["search_volume"] > 10000 and out["keyword_difficulty"] and out["serp"] and out["related_keywords"]
    assert call("/semrush/keywords/volume", keyword="email marketing", country="US")["search_volume"] > 10000
    ideas = call("/semrush/keywords/ideas", keyword="email marketing", country="US")
    assert ideas["count"] >= 10 and ideas["keywords"][0]["keyword"]
    serp = call("/semrush/keywords/serp", keyword="email marketing", country="US")
    assert serp["serp"][0]["results"] and serp["volatility"]
    rank = call("/semrush/keywords/rank", domain="mailchimp.com", keyword="email marketing", country="US")
    assert rank["is_ranking"] is True and rank["position"] and rank["domain_keywords"]


@tools
def test_domain_tools():
    backlinks = call("/semrush/domains/backlinks", domain="mailchimp.com")
    assert backlinks["authority_score"] and backlinks["backlinks"][0]["source_link"]
    authority = call("/semrush/domains/authority", domain="mailchimp.com")
    assert authority["authority_score"]["value"] and authority["authority_score_history"]
    finder = call("/semrush/domains/competitor-finder", domain="mailchimp.com", country="US")
    assert finder["competitors"][0]["domain"]
    assert call("/semrush/domains/ai-traffic-report", domain="mailchimp.com")["platforms"]
    assert call("/semrush/domains/ai-visibility", domain="mailchimp.com")["visibility_score"]
    audit = call("/semrush/pages/seo-audit", url="https://mailchimp.com/")
    assert audit["scores"]["total"] and audit["issues"] and audit["on_page_seo"]["title"]
