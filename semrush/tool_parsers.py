"""Normalizers for Semrush's free-tools API results (the `data` object of
GET /free-tools/api/v2/<tool>/?uid=…) -> the /semrush/keywords/* and
/semrush/domains/* tool responses. Same output conventions as parsers.py.

Deliberately dropped as noise: the task `uid`, `positions_type` (always
"all"), `serp_data` on the keyword tools when `grouped_serp_data` carries
the same rows grouped by SERP feature (the flat list is the "Organic"
group), `is_empty` / `task_status` / `created` / `updated` /
`search_engine` on the AI visibility report, the SEO audit's `thumbnail`
(always null), each check's `dynamic`/`hints`/`all_values` duplicates,
`heading_structure.value.structureTable[].barPercent` (a chart width) and
`keyword_density.messages[].customText` (repeated in the tabs), the
`competitor_level` copy of `competitor_relevance`.
"""
import html as html_lib

from semrush.parsers import INTENTS, _dict, _list, iso_date, percent, text, to_float, to_int

# Semrush SERP feature codes (the official API's numbering) — unknown codes
# are emitted as {"code": n, "name": null}.
SERP_FEATURES = {
    0: "instant answer", 1: "knowledge panel", 2: "carousel", 3: "local pack", 4: "top stories",
    5: "image pack", 6: "sitelinks", 7: "reviews", 8: "tweet", 9: "video", 10: "featured video",
    11: "featured snippet", 12: "amp", 13: "image", 14: "ads top", 15: "ads bottom", 16: "shopping ads",
    17: "hotels pack", 18: "jobs search", 19: "featured images", 20: "video carousel",
    21: "people also ask", 22: "faq", 23: "flights", 24: "find results on", 25: "recipes",
    26: "related topics", 27: "twitter carousel", 28: "indented", 29: "popular products",
    30: "related searches", 31: "related products", 32: "events", 33: "buying guide",
    34: "address pack", 35: "web stories", 36: "application", 37: "things to know",
    38: "explore brands", 39: "refine", 40: "short videos", 41: "product carousel",
    42: "shopping product", 43: "top sights", 44: "editorial reviews", 45: "discussions and forums",
    46: "what people are saying", 47: "perspectives", 48: "popular destinations",
    49: "things to do", 50: "hotels", 51: "flights carousel", 52: "ai overview",
}


def _feature(code):
    code = to_int(code)
    if code is None:
        return None
    return {"code": code, "name": SERP_FEATURES.get(code)}


def _intents(value):
    # names ("Informational") on the main keyword, official-API codes ([1]) on related_keywords
    out = []
    for i in _list(value):
        if isinstance(i, int) and not isinstance(i, bool):
            out.append(INTENTS.get(str(i), str(i)))
        elif isinstance(i, str) and i.strip():
            out.append(i.strip().lower())
    return out


def _serp_row(row):
    row = _dict(row)
    return {
        "position": to_int(row.get("position")),
        "link": text(row.get("url")),
        "domain": text(row.get("domain")),
        "authority_score": to_int(row.get("ascore")),
        "referring_domains_count": to_int(row.get("domains_num")),
        "backlinks_count": to_int(row.get("backlinks_num")),
        "page_keywords_count": to_int(row.get("url_keywords")),
        "search_traffic": to_int(row.get("search_traffic")),
        "serp_features": [f for f in (_feature(c) for c in _list(row.get("serp_features"))) if f],
    }


def _serp_groups(grouped):
    out = []
    for name, rows in _dict(grouped).items():
        rows = [_serp_row(r) for r in _list(rows) if isinstance(r, dict)]
        code = None
        for r in _list(_dict(grouped).get(name)):
            if isinstance(r, dict) and r.get("position_type") is not None:
                code = to_int(r.get("position_type"))
                break
        out.append({"feature": str(name).strip().lower(), "feature_code": code, "count": len(rows), "results": rows})
    return out


def _related(rows):
    return [
        {
            "keyword": text(r.get("keyword")),
            "search_volume": to_int(r.get("search_volume")),
            "keyword_difficulty": to_int(r.get("keyword_difficulty_index")),
            "cpc": to_float(r.get("cpc")),
            "currency": "USD",
            "intents": _intents(r.get("intent")),
        }
        for r in _list(rows) if isinstance(r, dict)
    ]


def _global_volume(rows):
    return [
        {"country": (text(r.get("country")) or "").lower() or None, "search_volume": to_int(r.get("search_volume"))}
        for r in _list(rows) if isinstance(r, dict)
    ]


# ---- keyword-checker / keyword-search-volume-checker ------------------------------------

def parse_keyword_overview(data, keyword, country):
    data = _dict(data)
    return {
        "keyword": text(data.get("keyword")) or keyword,
        "country": (text(data.get("country")) or country or "").upper() or None,
        "search_volume": to_int(data.get("search_volume")),
        "keyword_difficulty": to_int(data.get("keyword_difficulty_index")),
        "cpc": to_float(data.get("cpc")),
        "currency": "USD",
        "intents": _intents(data.get("intent")),
        "results_count": to_int(data.get("results")),
        "has_ai_overview": data.get("ai_overview_present") if isinstance(data.get("ai_overview_present"), bool) else None,
        "global_volume": _global_volume(data.get("global_volume_data")),
        "serp": _serp_groups(data.get("grouped_serp_data")),
        "related_keywords": _related(data.get("related_keywords")),
    }


# ---- keyword-tool (ideas) ---------------------------------------------------------------

def parse_keyword_ideas(data, keyword, country):
    data = _dict(data)
    metrics = _dict(data.get("keyword_metrics"))
    ideas = [
        {
            "keyword": text(r.get("keyword_phrase")),
            "search_volume": to_int(r.get("search_volume")),
            "keyword_difficulty": to_int(r.get("keyword_difficulty_index")),
            "cpc": to_float(r.get("cpc")),
            "currency": "USD",
            "intents": _intents(r.get("intent")),
        }
        for r in _list(data.get("keyword_data")) if isinstance(r, dict)
    ]
    return {
        "keyword": text(data.get("keyword")) or keyword,
        "country": (text(data.get("country")) or country or "").upper() or None,
        "related_keywords_count": to_int(metrics.get("related_keywords")),
        "is_related_count_capped": metrics.get("related_keywords_limit_reached") if isinstance(metrics.get("related_keywords_limit_reached"), bool) else None,
        "combined_search_volume": to_int(metrics.get("combined_search_volume")),
        "low_competition_keywords_count": to_int(metrics.get("low_competition_keywords")),
        "count": len(ideas),
        "keywords": ideas,
    }


# ---- serp-checker -------------------------------------------------------------------------

def parse_serp(data, keyword, country):
    data = _dict(data)
    return {
        "keyword": text(data.get("keyword")) or keyword,
        "country": (text(data.get("country")) or country or "").upper() or None,
        "results_count": to_int(data.get("results")),
        "serp": _serp_groups(data.get("serp_data")),
        "volatility": [
            {"date": iso_date(v.get("display_date")), "score": to_float(v.get("rank"))}
            for v in _list(data.get("volatility_data")) if isinstance(v, dict)
        ],
    }


# ---- keyword-rank-checker -------------------------------------------------------------------

def parse_keyword_rank(data, domain, keyword, country):
    data = _dict(data)
    pos = _dict(data.get("domain_position"))
    return {
        "domain": text(data.get("domain")) or domain,
        "keyword": text(data.get("keyword")) or keyword,
        "country": (text(data.get("country")) or country or "").upper() or None,
        "is_ranking": bool(pos.get("position")),
        "position": to_int(pos.get("position")),
        "link": text(pos.get("url")),
        "authority_score": to_int(pos.get("ascore")),
        "search_traffic": to_int(pos.get("traffic")),
        "backlinks_count": to_int(pos.get("backlinks")),
        "referring_domains_count": to_int(pos.get("ref_domains")),
        "page_keywords_count": to_int(pos.get("url_keywords")),
        "serp_features": [f for f in (_feature(c) for c in _list(pos.get("keyword_serp_features"))) if f],
        "keyword_overview": {
            "search_volume": to_int(_dict(data.get("keyword_overview")).get("search_volume")),
            "keyword_difficulty": to_int(_dict(data.get("keyword_overview")).get("keyword_difficulty_index")),
            "cpc": to_float(_dict(data.get("keyword_overview")).get("cpc")),
            "currency": "USD",
        } if data.get("keyword_overview") else None,
        "domain_keywords": [
            {
                "keyword": text(k.get("keyword")),
                "position": to_int(k.get("position")),
                "link": text(k.get("url")),
                "search_volume": to_int(k.get("search_volume")),
                "traffic_share_percent": to_float(k.get("traffic"), 2),
            }
            for k in _list(data.get("domain_keywords")) if isinstance(k, dict)
        ],
        "serp": _serp_groups(data.get("serp_data")) if isinstance(data.get("serp_data"), dict)
        else [_serp_row(r) for r in _list(data.get("serp_data")) if isinstance(r, dict)],
    }


# ---- backlink-checker -----------------------------------------------------------------------

def _backlink(row):
    row = _dict(row)
    return {
        "source_link": text(row.get("link")),
        "source_title": text(row.get("link_title")),
        "target_link": text(row.get("target_link")),
        "anchor": text(row.get("anchor")),
        "page_score": to_int(row.get("page_score")),
        "is_nofollow": bool(row.get("nofollow")),
        "is_new": bool(row.get("newlink")),
        "is_lost": bool(row.get("lostlink")),
    }


def parse_backlinks_report(data, domain):
    data = _dict(data)
    overview = _dict(data.get("backlinks_overview"))
    rows = [_backlink(r) for r in _list(data.get("backlinks_list")) if isinstance(r, dict)]
    return {
        "domain": text(data.get("domain")) or domain,
        "date": iso_date(data.get("display_date")),
        "authority_score": to_int(overview.get("ascore")),
        "backlinks_count": to_int(overview.get("total")),
        "referring_domains_count": to_int(overview.get("domains_num")),
        "dofollow_percent": to_float(overview.get("dofollow_percent"), 2),
        "count": len(rows),
        "backlinks": rows,
    }


# ---- website-authority-checker ---------------------------------------------------------------

def _diff_metric(block):
    block = _dict(block)
    if not block:
        return None
    return {"value": to_int(block.get("value")), "change_percent": percent(block.get("value_diff_percent"))}


def _pages(rows):
    return [
        {"link": text(r.get("url")), "referring_domains_count": to_int(r.get("domains_num")),
         "backlinks_count": to_int(r.get("backlinks_num"))}
        for r in _list(rows) if isinstance(r, dict)
    ]


def parse_authority(data, domain):
    data = _dict(data)
    score = _dict(data.get("backlink_score_metrics"))
    return {
        "domain": text(data.get("domain")) or domain,
        "date": iso_date(data.get("display_date")),
        "authority_score": _diff_metric(data.get("authority_score")),
        "backlinks": _diff_metric(data.get("backlinks")),
        "referring_domains": _diff_metric(data.get("referring_domains")),
        "organic_traffic": _diff_metric(data.get("traffic_organic")),
        "score_breakdown": {
            "health": (text(score.get("health_label")) or "").lower() or None,
            "link_power": to_float(score.get("link_power"), 2),
            "link_power_percent": to_float(score.get("link_power_percent"), 2),
            "natural_profile": to_float(score.get("natural_profile"), 2),
            "natural_profile_percent": to_float(score.get("natural_profile_percent"), 2),
            "organic_traffic": to_float(score.get("organic_traffic"), 2),
            "organic_traffic_percent": to_float(score.get("organic_traffic_percent"), 2),
        } if score else None,
        "authority_score_history": [
            {"date": iso_date(h.get("display_date")), "authority_score": to_int(h.get("authority_score"))}
            for h in _list(data.get("authority_score_history")) if isinstance(h, dict)
        ],
        "backlinks_history": [
            {"date": iso_date(h.get("display_date")), "backlinks": to_int(h.get("backlinks"))}
            for h in _list(data.get("backlinks_history")) if isinstance(h, dict)
        ],
        "referring_domains_history": [
            {"date": iso_date(h.get("display_date")), "referring_domains": to_int(h.get("referring_domains"))}
            for h in _list(data.get("referring_domains_history")) if isinstance(h, dict)
        ],
        "top_pages_by_backlinks": _pages(data.get("top_pages_by_backlinks")),
        "top_pages_by_referring_domains": _pages(data.get("backlink_indexed_pages")),
        "top_competitors": [
            {"domain": text(c.get("domain")), "authority_score": to_int(c.get("authority_score")),
             "common_keywords_count": to_int(c.get("common_keywords"))}
            for c in _list(data.get("top_competitors_by_authority_score")) if isinstance(c, dict)
        ],
    }


# ---- competitor-finder -------------------------------------------------------------------------

def parse_competitor_finder(data, domain, country):
    data = _dict(data)
    rows = [
        {
            "domain": text(r.get("competitor_domain")),
            "relevance_percent": percent(r.get("competitor_relevance")),
            "common_keywords_count": to_int(r.get("common_keywords")),
            "organic_keywords_count": to_int(r.get("organic_keywords")),
            "organic_traffic": to_int(r.get("organic_traffic")),
        }
        for r in _list(data.get("domain_data")) if isinstance(r, dict)
    ]
    return {
        "domain": text(data.get("website")) or domain,
        "country": (text(data.get("country")) or country or "").upper() or None,
        "count": len(rows),
        "competitors": rows,
    }


# ---- ai-traffic-checker ------------------------------------------------------------------------

def parse_ai_traffic_report(data, domain):
    data = _dict(data)
    summary = _dict(data.get("summary"))
    by_platform = _dict(data.get("ai_traffic_by_platform"))
    history = _dict(data.get("ai_traffic_history"))
    overviews = _dict(data.get("ai_overviews"))
    return {
        "domain": text(data.get("domain")) or domain,
        "date": iso_date(data.get("display_date")),
        "country": text(data.get("country")),
        "ai_traffic": to_int(summary.get("estimated_ai_traffic")),
        "ai_traffic_share_percent": to_float(summary.get("ai_traffic_share"), 2),
        "ai_citations_count": to_int(summary.get("ai_citations")),
        "ai_traffic_change_percent": to_float(history.get("change_percent"), 2),
        "ai_traffic_history": [
            {"date": iso_date(h.get("date")), "visits": to_int(h.get("traffic"))}
            for h in _list(history.get("items")) if isinstance(h, dict)
        ],
        "top_platform": text(by_platform.get("top_platform")),
        "platforms": [
            {"platform": text(p.get("platform")), "visits": to_int(p.get("traffic")), "share_percent": to_float(p.get("share"), 2)}
            for p in _list(by_platform.get("items")) if isinstance(p, dict)
        ],
        "traffic_by_channel": [
            {"channel": text(c.get("channel")), "visits": to_int(c.get("traffic")), "share_percent": to_float(c.get("share"), 2)}
            for c in _list(_dict(data.get("traffic_by_channel")).get("items")) if isinstance(c, dict)
        ],
        "ai_overviews": {
            "positions_count": to_int(overviews.get("positions")),
            "estimated_monthly_visits": to_int(overviews.get("estimated_monthly_traffic")),
            "change_percent": to_float(overviews.get("change_percent"), 2),
            "history": [
                {"date": iso_date(h.get("date")), "visits": to_int(h.get("traffic"))}
                for h in _list(overviews.get("history")) if isinstance(h, dict)
            ],
        } if overviews else None,
        "top_pages": [
            {"link": text(p.get("url")), "ai_visits": to_int(p.get("ai_visits")),
             "top_platforms": [text(x) for x in _list(p.get("top_platforms")) if text(x)]}
            for p in _list(_dict(data.get("top_pages")).get("items")) if isinstance(p, dict)
        ],
        "ai_search_visibility": [
            {"platform": text(v.get("platform")), "mentions_count": to_int(v.get("mentions")),
             "cited_pages_count": to_int(v.get("cited_pages"))}
            for v in _list(_dict(data.get("ai_search_visibility")).get("items")) if isinstance(v, dict)
        ],
    }


# ---- ai-visibility-checker ------------------------------------------------------------------------

def _engine_rows(rows):
    return [
        {"engine": text(r.get("engine")), "name": text(r.get("label")), "value": to_int(r.get("value"))}
        for r in _list(rows) if isinstance(r, dict)
    ]


def parse_ai_visibility(data, domain):
    data = _dict(data)
    return {
        "domain": text(data.get("domain")) or domain,
        "visibility_score": to_int(data.get("AI_visibility_score")),
        "mentions_count": to_int(_dict(data.get("mentions")).get("total")),
        "citations_count": to_int(data.get("citations")),
        "estimated_audience": to_int(data.get("audience")),
        "responses_share_percent": to_float(data.get("percent_of_responses"), 2),
        "visibility_score_trend": [
            {"month": text(t.get("month")), "visibility_score": to_int(t.get("value"))}
            for t in _list(data.get("visibility_score_trend")) if isinstance(t, dict)
        ],
        "mentions_by_engine": _engine_rows(data.get("mentions_by_engine")),
        "citations_by_engine": _engine_rows(data.get("citations_by_engine")),
        "visibility_by_engine": _engine_rows(data.get("visibility_score_by_engine")),
        "competitors": [
            {"domain": text(c.get("domain")), "visibility_score": to_int(c.get("visibility_score")),
             "mentions_count": to_int(c.get("mentions_count")), "citations_count": to_int(c.get("citations")),
             "estimated_audience": to_int(c.get("estimated_ai_audience_reach"))}
            for c in _list(data.get("competitors") or data.get("competitor_visibility_comparison")) if isinstance(c, dict)
        ],
        "top_cited_pages": [
            {"link": text(p.get("page_url")), "responses_count": to_int(p.get("responses")),
             "cited_on": [text(x) for x in _list(p.get("cited_on")) if text(x)]}
            for p in _list(data.get("top_cited_pages")) if isinstance(p, dict)
        ],
        "best_topics": [
            {"topic": text(t.get("topic")), "topic_volume": to_int(t.get("topic_volume")),
             "responses_count": to_int(t.get("responses")), "mentions_count": to_int(t.get("mentions")),
             "citations_count": to_int(t.get("citations"))}
            for t in _list(data.get("best_performing_topics")) if isinstance(t, dict)
        ],
        "opportunities": [
            {"prompt": text(o.get("prompt")), "platform": text(o.get("platform")),
             "search_volume": to_int(o.get("search_volume")),
             "mentioned_brands_count": to_int(o.get("mentioned_brands_count")),
             "unique_sources_count": to_int(o.get("unique_sources_count"))}
            for o in _list(data.get("opportunities")) if isinstance(o, dict)
        ],
        "prompts": [
            {"prompt": text(o.get("prompt")), "platform": text(o.get("platform")),
             "search_volume": to_int(o.get("search_volume")),
             "mentioned_brands_count": to_int(o.get("mentioned_brands_count")),
             "unique_sources_count": to_int(o.get("unique_sources_count"))}
            for o in _list(data.get("prompts")) if isinstance(o, dict)
        ],
    }


# ---- seo-checker (site audit) ---------------------------------------------------------------------

def _messages(block):
    return [
        {"status": text(m.get("status")), "text": text(m.get("text"))}
        for m in _list(_dict(block).get("messages")) if isinstance(m, dict)
    ]


def _check(block, value=None):
    block = _dict(block)
    if not block:
        return None
    messages = _messages(block)
    statuses = [m["status"] for m in messages if m.get("status")]
    status = "fail" if "fail" in statuses else "warning" if "warning" in statuses else "pass" if statuses else None
    out = {"status": status, "value": value if value is not None else block.get("value"), "messages": messages}
    return out


def _len_check(block):
    block = _dict(block)
    # the checker HTML-escapes page text ("Email &amp; SMS"; `length` counts the unescaped title)
    out = _check(block, text(html_lib.unescape(block["value"]) if isinstance(block.get("value"), str) else None))
    if out is not None:
        out["length"] = to_int(_dict(block.get("dynamic")).get("length"))
    return out


def parse_seo_audit(data, url):
    data = _dict(data)
    tech = _dict(data.get("technical_seo"))
    onpage = _dict(data.get("on_page_seo"))
    offpage = _dict(data.get("off_page_seo"))
    social = _dict(data.get("social_media"))
    overview = _dict(data.get("overview"))
    density = _dict(_dict(onpage.get("keyword_density")).get("value"))
    headings = _dict(_dict(onpage.get("heading_structure")).get("value"))
    content = _dict(onpage.get("content"))

    def off_metric(block):
        block = _dict(block)
        out = _check(block, to_int(block.get("value")))
        if out is not None:
            out["competitor_average"] = to_int(block.get("competitor_avg"))
        return out

    return {
        "link": text(data.get("url")) or url,
        "domain": text(data.get("domain")),
        "status": text(data.get("status")),
        "scores": {
            "total": to_int(overview.get("total_score")),
            "on_page_seo": to_int(overview.get("on_page_seo")),
            "off_page_seo": to_int(overview.get("off_page_seo")),
            "technical_seo": to_int(overview.get("technical_seo")),
            "social_media": to_int(overview.get("social_media")),
        },
        "issues": [
            {"category": text(i.get("type")), "status": text(i.get("status")), "element": text(i.get("element")),
             "message": text(i.get("message"))}
            for i in _list(data.get("issues")) if isinstance(i, dict)
        ],
        "on_page_seo": {
            "title": _len_check(onpage.get("title")),
            "meta_description": _len_check(onpage.get("meta_description")),
            "h1": _len_check(onpage.get("h1")),
            "page_link": _len_check(onpage.get("url")),
            "images": {
                **(_check(onpage.get("images"), None) or {}),
                "value": None,
                "images_count": to_int(_dict(_dict(onpage.get("images")).get("dynamic")).get("length")),
                "missing_alt": [text(html_lib.unescape(v)) if isinstance(v, str) else (text(_dict(v).get("src")) or v)
                                for v in _list(_dict(onpage.get("images")).get("value"))],
            } if onpage.get("images") else None,
            "content": {
                **(_check(content, None) or {}),
                "value": None,
                "words_count": to_int(_dict(content.get("dynamic")).get("count")),
                "text_to_code_ratio_percent": to_float(_dict(content.get("dynamic")).get("ratio"), 2),
            } if content else None,
            "heading_structure": {
                **(_check(onpage.get("heading_structure"), None) or {}),
                "value": None,
                "counts": {text(f.get("level")).lower(): to_int(f.get("count"))
                           for f in _list(headings.get("frequencyTable")) if isinstance(f, dict) and text(f.get("level"))},
                "headings": [{"level": (text(h.get("level")) or "").lower() or None, "text": text(h.get("value"))}
                             for h in _list(headings.get("rawTable")) if isinstance(h, dict)],
            } if onpage.get("heading_structure") else None,
            "keyword_density": {
                **(_check(onpage.get("keyword_density"), None) or {}),
                "value": None,
                "groups": [
                    {"phrase_length": text(t.get("title")),
                     "phrases": [{"phrase": text(w.get("word")), "count": to_int(w.get("count")),
                                  "density_percent": to_float(w.get("density"), 2),
                                  "prominence_percent": to_float(w.get("prominence"), 2)}
                                 for w in _list(t.get("content")) if isinstance(w, dict)]}
                    for t in _list(density.get("tabs")) if isinstance(t, dict)
                ],
            } if onpage.get("keyword_density") else None,
        },
        "technical_seo": {
            "favicon": _check(tech.get("favicon"), text(_dict(tech.get("favicon")).get("value"))),
            "noindex": _check(tech.get("noindex")),
            "sitemap": _check(tech.get("sitemap"), [text(v) for v in _list(_dict(tech.get("sitemap")).get("value")) if text(v)]),
            "hreflang": _check(tech.get("hreflang"), [
                {"href": text(v.get("href")), "hreflang": text(v.get("hreflang"))}
                for v in _list(_dict(tech.get("hreflang")).get("value")) if isinstance(v, dict)]),
            "language": _check(tech.get("language"), text(_dict(tech.get("language")).get("value"))),
            "canonical": _check(tech.get("canonical"), text(_dict(tech.get("canonical")).get("value"))),
            "robots_txt": {
                **(_check(tech.get("robots_txt"), text(_dict(tech.get("robots_txt")).get("value"))) or {}),
                "rules": [{"type": text(r.get("type")), "value": text(r.get("value"))}
                          for r in _list(_dict(tech.get("robots_txt")).get("rules")) if isinstance(r, dict)],
            } if tech.get("robots_txt") else None,
            "structured_data": _check(tech.get("structured_data"),
                                      [text(v) if isinstance(v, str) else v for v in _list(_dict(tech.get("structured_data")).get("types"))]),
        },
        "off_page_seo": {
            "authority_score": off_metric(offpage.get("ascore")),
            "backlinks_count": off_metric(offpage.get("total")),
            "referring_domains_count": off_metric(offpage.get("domains_num")),
            "follow_nofollow_ratio": _check(offpage.get("follow_nofollow_ratio"), None),
        },
        "social_media": {
            network: _check(block, text(_dict(block).get("value")))
            for network, block in social.items() if isinstance(block, dict)
        },
        "page_performance": data.get("page_performance") if isinstance(data.get("page_performance"), dict) else None,
        "top_keywords": [
            {"keyword": text(k.get("keyword")), "position": to_int(k.get("rank")), "link": text(k.get("url")),
             "search_volume": to_int(k.get("volume")), "cpc": to_float(k.get("cpc")), "currency": "USD",
             "keyword_difficulty": to_float(k.get("keyword_diff")), "traffic_share_percent": to_float(k.get("traffic"), 2)}
            for k in _list(data.get("keyword_ranking")) if isinstance(k, dict)
        ],
        "top_pages": [
            {"link": text(p.get("url")), "referring_domains_count": to_int(p.get("domains_num")),
             "backlinks_count": to_int(p.get("backlinks_num")), "keywords_count": to_int(p.get("keywords_count")),
             "traffic_share_percent": to_float(p.get("traffic_percent"), 2)}
            for p in _list(data.get("top_pages")) if isinstance(p, dict)
        ],
        "competitors": [
            {"domain": text(c.get("competitor_domain")), "relevance_percent": percent(c.get("competitor_level")),
             "common_keywords_count": to_int(c.get("common_keywords"))}
            for c in _list(data.get("competitors_data")) if isinstance(c, dict)
        ],
        "top_backlinks": [_backlink(b) for b in _list(data.get("top_backlinks")) if isinstance(b, dict)],
        "created_at": text(data.get("created_at")),
        "updated_at": text(data.get("updated_at")),
    }
