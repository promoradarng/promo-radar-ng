"""Turns a product URL into your tracked affiliate link.

Each programme gives you a link format after approval. Update the functions below
to match exactly what your affiliate dashboard shows; the formats here are
placeholders with the usual shape.
"""

from urllib.parse import quote, urlparse, urlencode, parse_qsl, urlunparse

from . import config


def _add_params(url, **params):
    parts = urlparse(url)
    query = dict(parse_qsl(parts.query))
    query.update(params)
    return urlunparse(parts._replace(query=urlencode(query)))


def jumia(url, aff_id):
    # Jumia's KOL portal issues a tracking link per product; a redirect wrapper is common.
    return f"https://kol.jumia.com/api/click/link/{aff_id}?redirect={quote(url, safe='')}"


def konga(url, aff_id):
    return _add_params(url, k_id=aff_id)


def generic(url, aff_id):
    return _add_params(url, ref=aff_id, utm_source="promoradar", utm_medium="affiliate")


BUILDERS = {"jumia": jumia, "konga": konga}


def link_for(store_key: str, url: str) -> str:
    aff_id = config.AFFILIATE.get(store_key, "")
    if not aff_id:
        return url
    return BUILDERS.get(store_key, generic)(url, aff_id)
