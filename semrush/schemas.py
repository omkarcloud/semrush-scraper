"""Marshmallow request schemas for every /semrush/* route. Generic fields
come from the shared schema_fields.py; this module adds the Semrush
resolvers. Every schema's load() output is the kwargs dict its endpoint
function takes.

ONE param per input (tripadvisor QueryOrIdField convention, never a sibling
`url`/`id` pair):

    domain     a domain name (amazon.com), any link to the site
               (https://www.amazon.com/dp/…) OR a semrush.com/website/<domain> link
    domains    comma-separated domains / links (max 10)
    keyword    free text (1-200 chars)
    country    for the top-websites list: a 2-letter ISO code or "global";
               for the keyword tools: a 2-letter ISO code (default US)
    category   top-websites: a category slug (online-services), its name or "all";
               popular: books | board-games | people | beer-brands | foods
    url        an http(s) page link (the SEO audit)
"""
from marshmallow import missing, validate

from schema_fields import BaseSchema, ChoiceField, CountryCodeField, QueryField, RefField, UrlField
from semrush import refs


# ---- id-or-link fields -------------------------------------------------------------

class DomainField(RefField):
    resolver = staticmethod(refs.resolve_domain)


class DomainListField(RefField):
    resolver = staticmethod(refs.resolve_domains)


class TrendingCountryField(RefField):
    resolver = staticmethod(refs.resolve_country)

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", "global")
        super().__init__(**kwargs)


class TrendingCategoryField(RefField):
    resolver = staticmethod(refs.resolve_category)

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", "all")
        super().__init__(**kwargs)


class PopularCategoryField(RefField):
    resolver = staticmethod(refs.resolve_popular)


class KeywordCountryField(CountryCodeField):
    """ISO-2, default US (the keyword tools' database)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("load_default", "US")
        super().__init__(**kwargs)


# ---- domains -------------------------------------------------------------------------

class DomainSchema(BaseSchema):
    domain = DomainField()


class DomainBatchSchema(BaseSchema):
    domains = DomainListField()


# ---- discovery -----------------------------------------------------------------------

class TopWebsitesSchema(BaseSchema):
    country = TrendingCountryField()
    category = TrendingCategoryField()


class EmptySchema(BaseSchema):
    """Routes without parameters (reference lists)."""


class PopularSchema(BaseSchema):
    category = PopularCategoryField()


class AutocompleteSchema(BaseSchema):
    query = QueryField(max_length=100)
    type = ChoiceField(["keywords", "domains"], load_default="keywords")


# ---- keyword tools (free-tools API, captcha-gated) --------------------------------------

class KeywordSchema(BaseSchema):
    keyword = QueryField(max_length=200)
    country = KeywordCountryField()


class KeywordRankSchema(BaseSchema):
    domain = DomainField()
    keyword = QueryField(max_length=200)
    country = KeywordCountryField()


class DomainCountrySchema(BaseSchema):
    domain = DomainField()
    country = KeywordCountryField()


class UrlSchema(BaseSchema):
    url = UrlField(required=True, load_default=missing, validate=validate.Length(max=2000))
