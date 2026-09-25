"""One param per input (tripadvisor QueryOrIdField convention): every
resolver takes a bare value OR a semrush.com / site link and hands back
what the page fetchers need. Each raises ValueError with a user-facing
message; schemas.py wraps them as RefField subclasses.

    resolve_domain    "amazon.com" | "www.amazon.com" | "https://amazon.com/dp/x"
                      | https://www.semrush.com/website/amazon.com/overview/
                      -> "amazon.com"   (lower-cased host, leading www. dropped)
    resolve_domains   comma list of the above (max 10)
    resolve_country   "us" | "US" | "global" -> "us" | "global"
    resolve_category  "Online Services" | "online-services" | "all" -> "online-services"
    resolve_popular   "books" | https://www.semrush.com/popular/books/ -> "books"
"""
import re
from urllib.parse import unquote, urlparse

SITE = "https://www.semrush.com"
POPULAR_CATEGORIES = ("books", "board-games", "people", "beer-brands", "foods")

_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}$")
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SEMRUSH_HOSTS = ("semrush.com", "www.semrush.com")


def _host_of(value):
    raw = value if value.lower().startswith(("http://", "https://")) else \
        ("https:" + value if value.startswith("//") else "https://" + value)
    parsed = urlparse(raw)
    return (parsed.hostname or "").lower(), [unquote(s) for s in parsed.path.split("/") if s]


def resolve_domain(value):
    value = str(value or "").strip()
    if not value:
        raise ValueError("domain is required")
    host, segments = _host_of(value)
    if (host in _SEMRUSH_HOSTS or host.endswith(".semrush.com")) and segments:
        # https://www.semrush.com/website/amazon.com/overview/  (any locale host);
        # a bare "semrush.com" is just that domain
        low = [s.lower() for s in segments]
        if len(low) >= 2 and low[0] == "website":
            host = low[1]
        else:
            raise ValueError("domain must be a domain name (amazon.com), a website link or a semrush.com/website/<domain> link")
    host = host.strip(".").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host or not _DOMAIN_RE.match(host):
        raise ValueError("domain must be a domain name like amazon.com (or any link to the site)")
    return host


def resolve_domains(value, max_items=10):
    out = []
    for raw in str(value or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        domain = resolve_domain(raw)
        if domain not in out:
            out.append(domain)
    if not out:
        raise ValueError("domains is required")
    if len(out) > max_items:
        raise ValueError(f"at most {max_items} domains")
    return out


def root_domain_hint(domain):
    """A shorter candidate when a page is missing for a subdomain
    (support.google.com -> google.com; amazon.co.uk stays). Only a hint for
    the 404 message — never substituted silently."""
    labels = domain.split(".")
    if len(labels) <= 2:
        return None
    two_level = {"co", "com", "net", "org", "gov", "edu", "ac"}
    if labels[-2] in two_level and len(labels[-1]) == 2:
        # amazon.co.uk is already a root; news.bbc.co.uk -> bbc.co.uk
        return ".".join(labels[-3:]) if len(labels) > 3 else None
    return ".".join(labels[-2:])


def resolve_country(value):
    """ISO-2 code or 'global' (case-insensitive) for the trending lists."""
    value = str(value or "").strip().lower()
    if not value:
        return "global"
    if value in ("global", "world", "worldwide", "all"):
        return "global"
    if len(value) == 2 and value.isalpha():
        return value
    raise ValueError("country must be a 2-letter ISO code (us, gb, in, ...) or 'global'")


def resolve_category(value):
    """A trending-websites category: slug ('online-services'), display name
    ('Online Services') or 'all'."""
    value = str(value or "").strip().lower()
    if not value or value == "all":
        return "all"
    slug = re.sub(r"[^a-z0-9]+", "-", value.replace("&", " and ")).strip("-")
    if not _SLUG_RE.match(slug):
        raise ValueError("category must be a category slug (online-services) or name, or 'all'")
    return slug


def resolve_popular(value):
    value = str(value or "").strip()
    if not value:
        raise ValueError("category is required")
    host, segments = _host_of(value)
    if host in _SEMRUSH_HOSTS or host.endswith(".semrush.com"):
        low = [s.lower() for s in segments]
        if len(low) >= 2 and low[0] == "popular":
            value = low[1]
        else:
            raise ValueError("category link must look like https://www.semrush.com/popular/books/")
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    aliases = {"book": "books", "game": "board-games", "games": "board-games", "boardgames": "board-games",
               "person": "people", "beer": "beer-brands", "beers": "beer-brands", "food": "foods"}
    slug = aliases.get(slug, slug)
    if slug not in POPULAR_CATEGORIES:
        raise ValueError("category must be one of: " + ", ".join(POPULAR_CATEGORIES))
    return slug


# ---- links -------------------------------------------------------------------------------

def website_link(domain, tab="overview"):
    return f"{SITE}/website/{domain}/{tab}/" if domain else None


def trending_link(country, category):
    return f"{SITE}/trending-websites/{country}/{category}"


def popular_link(slug):
    return f"{SITE}/popular/{slug}/"
