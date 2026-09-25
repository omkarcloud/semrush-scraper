"""Semrush transport: plain curl_cffi with browser-impersonated TLS against
www.semrush.com's PUBLIC surfaces. No browser, no cookies, no login
(validated 2026-09-25 from direct Indian egress: 15 domain pages in 23 s,
every status 200, no throttling headers; the server is plain nginx — no
Cloudflare / DataDome / Akamai anywhere on the host).

Open surfaces (semrush/domains.py, semrush/discover.py):

  * /website/<root-domain>/overview/ and /competitors/ — Astro SSR pages
    whose whole dataset sits in ONE <astro-island props="…"> attribute
    (HTML-escaped JSON in Astro's [type, value] tuple encoding). Root
    domains only; subdomains, paths and unknown domains answer 404.
    `?device=mobile` is the only working query switch.
  * /trending-websites/<global|cc>/<all|category> — window.__PRELOADED_STATE__
    JSON: ~100 domains per (country x category) plus a 12-month market
    series, the 240 country codes and 111 category slugs.
  * /popular/<books|people|foods|beer-brands|board-games>/ — Astro props:
    ~450 keywords with volume / KD / CPC / rank, refreshed monthly.
  * /search-bar/api/search/suggestions?q=&type=2 — keyword autocomplete JSON.

Captcha-gated surface (semrush/keywords.py + semrush/captcha.py): the
free-tools JSON API (POST /free-tools/api/v2/<tool>/ then GET ?uid=) wants
a reCAPTCHA Enterprise v3 token minted by a real browser; the transport
below only carries the requests, the token dance lives in captcha.py.

Blocks: none seen. If the pod's egress ever starts answering 403 / 429,
a worker moves its session to a sticky residential exit
(config.semrush_fallback_proxy()) for config.SEMRUSH_BLOCK_COOLDOWN
seconds — the twitch / kick shape.

Failure taxonomy (scraper_errors, mapped to HTTP by route_glue):
  SemrushUpstreamError  transport failure / 5xx / unparsable page  — retryable
  SemrushBlocked        403 / 429 / captcha refused                — retryable on a new exit
  SemrushBadRequest     upstream rejected the params               — never retried
  SemrushNotFound       no page for that domain / list             — never retried
"""
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError

SITE = "https://www.semrush.com"
IMPERSONATE = "chrome"
TIMEOUT = 45
FANOUT_WORKERS = 6
RETRIES = 3

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "upgrade-insecure-requests": "1",
}
JSON_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "referer": SITE + "/",
}


class SemrushUpstreamError(UpstreamError):
    """Transport failure, 5xx or a page that no longer carries its data — retryable."""


class SemrushBlocked(SemrushUpstreamError, Blocked):
    """403 / 429 — retryable on a fresh exit."""


class SemrushBadRequest(BadRequest):
    """Upstream rejected the params. Never retried."""


class SemrushNotFound(NotFound):
    """No Semrush page for that domain / keyword list — never retried."""


# ---- sessions ------------------------------------------------------------------
# One curl session per worker thread. Direct egress by default; after a block
# the thread's sessions go through a sticky residential exit for a cooldown.
_local = threading.local()
_fallback_until = 0.0
_fallback_lock = threading.Lock()


def _proxy_for_new_session():
    forced = config.semrush_proxy()
    if forced:
        return forced
    if time.time() < _fallback_until:
        return config.semrush_fallback_proxy()
    return None


def _session():
    sess = getattr(_local, "session", None)
    if sess is None:
        from curl_cffi import requests as curl_requests
        sess = curl_requests.Session(impersonate=IMPERSONATE)
        proxy = _proxy_for_new_session()
        if proxy:
            sess.proxies = {"http": proxy, "https": proxy}
        _local.session = sess
    return sess


def _drop_session():
    sess = getattr(_local, "session", None)
    _local.session = None
    if sess is not None:
        try:
            sess.close()
        except Exception:
            pass


def _note_block():
    """A 403/429 on direct egress: send new sessions through a residential
    exit for a while (no-op when no fallback country is configured)."""
    global _fallback_until
    if config.semrush_fallback_proxy() is not None:
        with _fallback_lock:
            _fallback_until = time.time() + config.SEMRUSH_BLOCK_COOLDOWN


def dump_debug(name, text):
    """Keep the last body of each failure kind when SEMRUSH_DEBUG_DIR is set."""
    d = os.environ.get("SEMRUSH_DEBUG_DIR")
    if not d:
        return
    try:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{name}.txt"), "w") as f:
            f.write(text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, indent=1))
    except Exception:
        pass


def _retrying(once):
    last = None
    for attempt in range(RETRIES):
        try:
            return once()
        except (SemrushBadRequest, SemrushNotFound):
            raise
        except SemrushUpstreamError as e:
            last = e
            _drop_session()
            time.sleep(0.5 * (attempt + 1))
    raise last


def get_html(path, params=None, *, label=None, missing=None, referer=None):
    """GET a www.semrush.com page -> its HTML text. 404 -> SemrushNotFound
    (`missing` is the user-facing message)."""
    url = path if path.startswith("http") else SITE + path
    label = label or path

    def once():
        sess = _session()
        headers = dict(HEADERS)
        if referer:
            headers["referer"] = referer
        try:
            resp = sess.get(url, params=params, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        except Exception as e:
            raise SemrushUpstreamError(f"{label}: request failed: {type(e).__name__}: {e}")
        return _check(resp, label, missing)
    return _retrying(once)


def get_json(path, params=None, *, label=None, missing=None, headers=None):
    """GET a JSON endpoint on www.semrush.com -> parsed body."""
    url = path if path.startswith("http") else SITE + path
    label = label or path

    def once():
        sess = _session()
        hdrs = dict(JSON_HEADERS)
        if headers:
            hdrs.update(headers)
        try:
            resp = sess.get(url, params=params, headers=hdrs, timeout=TIMEOUT)
        except Exception as e:
            raise SemrushUpstreamError(f"{label}: request failed: {type(e).__name__}: {e}")
        text = _check(resp, label, missing)
        try:
            return json.loads(text)
        except ValueError:
            dump_debug("notjson", text)
            raise SemrushUpstreamError(f"{label}: response is not JSON")
    return _retrying(once)


def request_json(method, url, *, json_body=None, params=None, headers=None, proxy=None,
                 label=None, timeout=TIMEOUT):
    """One JSON request on an explicit session/proxy (the free-tools API,
    whose calls must share one egress with the captcha token). Returns
    (status, parsed body or None, headers)."""
    from curl_cffi import requests as curl_requests
    sess = curl_requests.Session(impersonate=IMPERSONATE)
    if proxy:
        sess.proxies = {"http": proxy, "https": proxy}
    try:
        resp = sess.request(method, url, json=json_body, params=params, headers=headers, timeout=timeout)
    except Exception as e:
        raise SemrushUpstreamError(f"{label or url}: request failed: {type(e).__name__}: {e}")
    finally:
        try:
            sess.close()
        except Exception:
            pass
    try:
        body = resp.json()
    except Exception:
        body = None
    return resp.status_code, body, dict(resp.headers)


def _check(resp, label, missing):
    status = resp.status_code
    text = resp.text or ""
    if status == 404:
        raise SemrushNotFound(missing or f"{label}: not found")
    if status in (403, 429):
        _note_block()
        dump_debug("blocked", text)
        raise SemrushBlocked(f"HTTP {status} on {label}")
    if status >= 500:
        raise SemrushUpstreamError(f"HTTP {status} on {label}")
    if status >= 400:
        raise SemrushBadRequest(f"HTTP {status} on {label}")
    return text


# ---- fan-out ------------------------------------------------------------------------

def run_parallel(fns, workers=FANOUT_WORKERS):
    if not fns:
        return []
    if len(fns) == 1:
        return [fns[0]()]
    with ThreadPoolExecutor(max_workers=min(workers, len(fns))) as ex:
        futures = [ex.submit(fn) for fn in fns]
        return [f.result() for f in futures]


if __name__ == "__main__":
    # Smoke test: python semrush/fetch.py [domain]
    domain = sys.argv[1] if len(sys.argv) > 1 else "amazon.com"
    html = get_html(f"/website/{domain}/overview/", missing=f"no semrush page for {domain}")
    print(len(html), "bytes;", "astro-island" in html)
