"""Configuration for the Semrush Scraper. Everything can be set with an
environment variable; the defaults work out of the box.

    PORT            port the API listens on (default 8000)
    SEMRUSH_PROXY   proxy URL for every request, e.g. http://user:pass@host:port
                    (default: none — direct). The domain, top-websites, popular
                    and autocomplete endpoints never needed one in our tests.
                    The keyword / backlink / authority / AI / SEO audit tools
                    are capped by Semrush PER IP PER DAY (5, 3 or 1 calls per
                    tool), so for more than a handful of those calls a day, set
                    a ROTATING residential proxy here: each call opens a fresh
                    connection, and a rotating gateway gives it a fresh IP.

Everything else below is a plain constant with a working default — edit it
here if you need to.
"""
import os

PORT = int(os.environ.get("PORT", "8000"))

# Retry policy for transport errors and blocks (every request).
MAX_RETRIES = 3
RETRY_BACKOFF = 2          # seconds, multiplied by the attempt number

SEMRUSH_PROXY = os.environ.get("SEMRUSH_PROXY") or None

# A blocked page request (403 / 429) switches new sessions to SEMRUSH_PROXY
# for this many seconds when one is set.
SEMRUSH_BLOCK_COOLDOWN = 900

# Free-tools API (keyword / backlink / authority / AI / SEO audit endpoints).
SEMRUSH_TOOL_ATTEMPTS = 3          # connections tried per call (a 429 = that IP's daily quota is spent)
SEMRUSH_TOOL_POLL_TIMEOUT = 90     # seconds to wait for a task result
SEMRUSH_BROWSER_IDLE = 600         # seconds without a captcha mint before the browser closes
SEMRUSH_MINT_TIMEOUT = 30          # seconds for one reCAPTCHA token


def semrush_proxy():
    """Proxy for the page requests (None = direct)."""
    return os.environ.get("SEMRUSH_PROXY") or None


def semrush_fallback_proxy():
    """Proxy a blocked page request moves to (None = no fallback)."""
    return os.environ.get("SEMRUSH_PROXY") or None


def semrush_tool_proxy():
    """Proxy for ONE free-tools call (None = direct)."""
    return os.environ.get("SEMRUSH_PROXY") or None


def semrush_mint_proxy():
    """The captcha browser always runs on your own connection."""
    return None
