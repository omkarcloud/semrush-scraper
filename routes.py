"""The 28 Semrush endpoints. Every path is served with and without the
`/semrush` prefix, so code generated against the hosted API (paths like
/domains/overview) runs unchanged against this server.

Params are validated by the module's marshmallow schemas
(semrush/schemas.py): bad params -> 400, no data for that domain / list ->
404, anything upstream -> 500."""
import json

from bottle import request, response, route

from schema_fields import load_query
from scraper_errors import BadRequest, NotFound
from semrush import discover, domains, keywords
from semrush import schemas as S


def json_response(data, status=200):
    response.status = status
    response.content_type = "application/json"
    return json.dumps(data, ensure_ascii=False)


def query_dict():
    """The request query as unicode strings (bottle 0.12's .get() hands back
    latin-1 decoded bytes, so a UTF-8 "Amélie" would arrive as "AmÃ©lie")."""
    return {key: request.query.getunicode(key) for key in request.query.keys()}


def call(label, schema, fn):
    """Validate the query with `schema`, run fn(**params), map failures."""
    params, error = load_query(schema, query_dict())
    if error:
        return json_response(error, 400)
    try:
        return json_response(fn(**params))
    except ValueError as e:                # bad params
        return json_response({"error": str(e)}, 400)
    except BadRequest as e:                # Semrush rejected the request
        return json_response({"error": f"semrush rejected the request: {e}"}, 400)
    except NotFound as e:
        return json_response({"error": str(e) or "not found"}, 404)
    except Exception as e:                 # retries exhausted / blocked
        return json_response({"error": f"semrush {label} failed: {e}"}, 500)


ENDPOINTS = [
    ("/domains/overview", S.DomainSchema, domains.overview),
    ("/keywords/overview", S.KeywordSchema, keywords.overview),
    ("/keywords/autocomplete", S.AutocompleteSchema, discover.autocomplete),
    ("/keywords/volume", S.KeywordSchema, keywords.volume),
    ("/keywords/ideas", S.KeywordSchema, keywords.ideas),
    ("/keywords/serp", S.KeywordSchema, keywords.serp),
    ("/keywords/rank", S.KeywordRankSchema, keywords.rank),
    ("/domains/rank", S.DomainSchema, domains.rank),
    ("/domains/traffic", S.DomainSchema, domains.traffic),
    ("/domains/traffic-by-country", S.DomainSchema, domains.traffic_by_country),
    ("/domains/traffic-sources", S.DomainSchema, domains.traffic_sources),
    ("/domains/search-traffic", S.DomainSchema, domains.search_traffic),
    ("/domains/top-keywords", S.DomainSchema, domains.top_keywords),
    ("/domains/ai-traffic", S.DomainSchema, domains.ai_traffic),
    ("/domains/ai-traffic-report", S.DomainSchema, keywords.ai_traffic_report),
    ("/domains/ai-visibility", S.DomainSchema, keywords.ai_visibility),
    ("/domains/backlinks-overview", S.DomainSchema, domains.backlinks_overview),
    ("/domains/backlinks", S.DomainSchema, keywords.backlinks),
    ("/domains/authority", S.DomainSchema, keywords.authority),
    ("/domains/competitors", S.DomainSchema, domains.competitors),
    ("/domains/competitor-finder", S.DomainCountrySchema, keywords.competitor_finder),
    ("/domains/related", S.DomainSchema, domains.related),
    ("/domains/batch", S.DomainBatchSchema, domains.batch),
    ("/pages/seo-audit", S.UrlSchema, keywords.seo_audit),
    ("/top-websites", S.TopWebsitesSchema, discover.top_websites),
    ("/top-websites/categories", S.EmptySchema, discover.top_website_categories),
    ("/top-websites/countries", S.EmptySchema, discover.top_website_countries),
    ("/popular", S.PopularSchema, discover.popular),
]


def mount(path, schema, fn):
    """Serve an endpoint at /path and /semrush/path."""
    label = path.strip("/")

    def handler():
        return call(label, schema, fn)
    handler.__name__ = "semrush_" + label.replace("/", "_").replace("-", "_")
    route(path, method="GET")(handler)
    route("/semrush" + path, method="GET")(handler)


for _path, _schema, _fn in ENDPOINTS:
    mount(_path, _schema, _fn)


@route("/", method="GET")
@route("/health", method="GET")
def health():
    return json_response({"status": "ok", "endpoints": [p for p, _, _ in ENDPOINTS]})
