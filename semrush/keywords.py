"""/semrush/keywords/* and the tool-backed /semrush/domains/* routes:
Semrush's free-tools JSON API (the engine behind the site's free Keyword
Overview / Keyword Magic preview / SERP checker / rank checker / backlink
checker / authority checker / competitor finder / AI traffic + visibility
checkers / SEO checker).

Wire protocol (semrush/fetch.py carries it, semrush/captcha.py mints):

    POST https://www.semrush.com/free-tools/api/v2/<tool>/
         {…params, "recaptcha_v3": <token>}          -> 202 {"uid": …}
    GET  https://www.semrush.com/free-tools/api/v2/<tool>/?uid=<uid>
         -> 202 while the task runs, 200 {"uid", "data": {...}} when done

Every tool is capped PER EXIT IP per day (x-ratelimit-limit: 5 for the
keyword tools, 3 for keyword-tool / rank checker / AI tools, 1 for the
backlink and SEO checkers; 429 "Daily attempt limit exceeded" after
that), so each call goes through a FRESH sticky residential exit
(config.semrush_tool_proxy()) and a 429 just moves to the next exit. The
token comes from the shared headed browser on direct egress — Semrush
does not bind it to the POSTing IP. Results are served from Semrush's
own cache for repeated queries (same uid comes back), and ours keeps
them for cache_config.TOOL_CACHE.
"""
import time

import config
from semrush import captcha
from semrush import tool_parsers as TP
from semrush.fetch import (SITE, SemrushBadRequest, SemrushBlocked, SemrushNotFound, SemrushUpstreamError,
                           dump_debug, request_json)

API = SITE + "/free-tools/api"
POLL_INTERVAL = 2.0
REQUEST_TIMEOUT = 40       # seconds per POST / poll GET (a residential exit that takes longer is dead)
POLL_TRANSPORT_RETRIES = 3

# tool -> the page whose referer the browser sends (only cosmetic: any token
# is accepted by any tool, the referer just matches what the site does)
PAGES = {
    "keyword-checker": SITE + "/analytics/keywordoverview/",
    "keyword-search-volume-checker": SITE + "/free-tools/keyword-search-volume-checker/",
    "keyword-tool": SITE + "/analytics/keywordmagic/",
    "serp-checker": SITE + "/free-tools/serp-checker/",
    "keyword-rank-checker": SITE + "/free-tools/keyword-rank-checker/",
    "backlink-checker": SITE + "/analytics/backlinks/",
    "website-authority-checker": SITE + "/free-tools/website-authority-checker/",
    "competitor-finder": SITE + "/free-tools/competitor-finder/",
    "ai-traffic-checker": SITE + "/free-tools/ai-traffic-checker/",
    "ai-visibility-checker": SITE + "/free-tools/ai-search-visibility-checker/",
    "seo-checker": SITE + "/free-tools/seo/",
}


def _headers(tool, ua):
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "origin": SITE,
        "referer": PAGES[tool],
        "user-agent": ua,
    }


def _message(body):
    if isinstance(body, dict):
        detail = body.get("detail") or body.get("message") or body.get("error")
        if isinstance(detail, str):
            return detail
        # DRF field errors: {"domain": ["This field is required."]}
        parts = [f"{k}: {' '.join(v) if isinstance(v, list) else v}" for k, v in body.items()]
        return "; ".join(parts)[:300]
    return None


def run_tool(tool, params, *, settle=None):
    """Submit a task and wait for its result -> the raw `data` dict.
    `settle(data)` may return False to keep polling (the SEO checker
    answers 200 with status "partial" first)."""
    label = f"free-tools/{tool}"
    attempts = max(1, config.SEMRUSH_TOOL_ATTEMPTS)
    last = None
    for attempt in range(attempts):
        try:
            token, ua = captcha.token()
        except captcha.CaptchaError as e:
            raise SemrushUpstreamError(f"{label}: {e}")
        proxy = config.semrush_tool_proxy()
        headers = _headers(tool, ua)
        try:
            status, body, resp_headers = request_json("POST", f"{API}/v2/{tool}/", json_body={**params, "recaptcha_v3": token},
                                                      headers=headers, proxy=proxy, label=label, timeout=REQUEST_TIMEOUT)
            if status in (200, 202) and isinstance(body, dict) and body.get("uid"):
                if isinstance(body.get("data"), dict) and body["data"] and (settle is None or settle(body["data"])):
                    return body["data"]
                return _poll(tool, body["uid"], headers, proxy, label, settle)
        except SemrushUpstreamError as e:
            # a dead / slow residential exit (curl 28 / 56) or a block while
            # polling: next exit (a repeated query answers the same uid)
            last = e
            continue
        message = _message(body) or ""
        if status == 429 or "attempt limit" in message.lower():
            # this exit's daily quota for the tool is spent: next exit
            last = SemrushBlocked(f"{label}: exit quota exhausted ({message or status})")
            continue
        if status == 400 and "recaptcha" in message.lower():
            # token rejected (expired / scored low): mint another on the next round
            last = SemrushBlocked(f"{label}: {message}")
            continue
        if status == 400:
            raise SemrushBadRequest(f"{label}: {message or 'rejected'}")
        if status == 404:
            raise SemrushNotFound(f"{label}: {message or 'no data'}")
        if status in (401, 403):
            last = SemrushBlocked(f"{label}: HTTP {status} {message}")
            continue
        dump_debug("tool_post", {"status": status, "body": body})
        last = SemrushUpstreamError(f"{label}: HTTP {status} {message}")
    raise last or SemrushUpstreamError(f"{label}: failed")


def _poll(tool, uid, headers, proxy, label, settle):
    deadline = time.monotonic() + config.SEMRUSH_TOOL_POLL_TIMEOUT
    partial = None
    transport_failures = 0
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL)
        try:
            status, body, _ = request_json("GET", f"{API}/v2/{tool}/", params={"uid": uid}, headers=headers,
                                           proxy=proxy, label=label, timeout=REQUEST_TIMEOUT)
        except SemrushUpstreamError:
            transport_failures += 1
            if transport_failures >= POLL_TRANSPORT_RETRIES:
                raise
            continue
        if status == 200 and isinstance(body, dict):
            data = body.get("data")
            if isinstance(data, dict) and data:
                if settle is None or settle(data):
                    return data
                partial = data
            elif body.get("error") or body.get("detail"):
                raise SemrushUpstreamError(f"{label}: {_message(body)}")
            continue
        if status == 202:
            continue
        if status == 404:
            raise SemrushNotFound(f"{label}: {_message(body) or 'no data for that query'}")
        if status in (400, 422):
            raise SemrushBadRequest(f"{label}: {_message(body) or 'rejected'}")
        if status in (403, 429):
            raise SemrushBlocked(f"{label}: HTTP {status} while polling")
        dump_debug("tool_poll", {"status": status, "body": body})
        raise SemrushUpstreamError(f"{label}: HTTP {status} while polling")
    if partial:
        return partial
    raise SemrushUpstreamError(f"{label}: no result within {config.SEMRUSH_TOOL_POLL_TIMEOUT}s")


# ---- keywords -------------------------------------------------------------------------

def overview(keyword, country):
    data = run_tool("keyword-checker", {"keyword": keyword, "country": country})
    return TP.parse_keyword_overview(data, keyword, country)


def volume(keyword, country):
    data = run_tool("keyword-search-volume-checker", {"keyword": keyword, "country": country})
    return TP.parse_keyword_overview(data, keyword, country)


def ideas(keyword, country):
    data = run_tool("keyword-tool", {"keyword": keyword, "country": country})
    return TP.parse_keyword_ideas(data, keyword, country)


def serp(keyword, country):
    data = run_tool("serp-checker", {"keyword": keyword, "country": country})
    return TP.parse_serp(data, keyword, country)


def rank(domain, keyword, country):
    data = run_tool("keyword-rank-checker", {"domain": domain, "keyword": keyword, "country": country})
    return TP.parse_keyword_rank(data, domain, keyword, country)


# ---- domains (tool-backed) --------------------------------------------------------------

def backlinks(domain):
    data = run_tool("backlink-checker", {"website": domain})
    return TP.parse_backlinks_report(data, domain)


def authority(domain):
    data = run_tool("website-authority-checker", {"website": domain})
    return TP.parse_authority(data, domain)


def competitor_finder(domain, country):
    data = run_tool("competitor-finder", {"website": domain, "country": country})
    return TP.parse_competitor_finder(data, domain, country)


def ai_traffic_report(domain):
    data = run_tool("ai-traffic-checker", {"website": domain})
    return TP.parse_ai_traffic_report(data, domain)


def ai_visibility(domain):
    data = run_tool("ai-visibility-checker", {"domain": domain})
    return TP.parse_ai_visibility(data, domain)


def seo_audit(url):
    data = run_tool("seo-checker", {"url": url}, settle=lambda d: (d.get("status") or "").lower() not in ("partial", "pending", "running"))
    return TP.parse_seo_audit(data, url)
