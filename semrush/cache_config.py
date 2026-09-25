"""Cache TTL per /semrush/* endpoint (cache.py, keyed on the validated params).

Semrush refreshes the public domain pages, the top-websites lists and the
popular keyword lists ONCE A MONTH (every block carries its data month),
so a day-long cache never serves stale data. The captcha-gated keyword
tools are kept much longer: every uncached call spends one of the 5 (or
1) daily attempts an exit IP gets, and their numbers are monthly too.
"""
from datetime import timedelta

DOMAIN_CACHE = timedelta(hours=24)        # /website/<domain>/* pages
TRENDING_CACHE = timedelta(hours=24)      # top-websites lists
REFERENCE_CACHE = timedelta(days=7)       # category / country lists
POPULAR_CACHE = timedelta(hours=24)       # /popular/* keyword lists
AUTOCOMPLETE_CACHE = timedelta(hours=6)
TOOL_CACHE = timedelta(days=7)            # free-tools keyword / backlink / audit results
