"""Runs every scraper, checks each deal is real, saves it, and exports deals.json for the app."""

import json
import logging
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from . import config, db, affiliate
from .scrapers import build
from .scrapers.base import Fetcher

log = logging.getLogger(__name__)


def guess_category(title: str) -> str:
    t = " " + title.lower() + " "
    for cat, words in config.CATEGORY_KEYWORDS.items():
        if any(w in t for w in words):
            return cat
    return "Other"


def check(deal, conn):
    """Return None if the deal is fine to show, or the reason it is hidden."""
    host = urlparse(deal.url).netloc
    if any(host.endswith(b) for b in config.BLOCKED_DOMAINS):
        return "blocked marketplace"
    if deal.price <= 0 or deal.old_price <= 0:
        return "missing price"
    if deal.discount_percent < config.MIN_DISCOUNT_PERCENT:
        return "discount too small"
    if deal.discount_percent >= 90:
        return "discount looks wrong"  # usually a scraping error or a typo on the shop
    past = db.history(conn, deal.id, config.FAKE_DISCOUNT_LOOKBACK_DAYS)
    if past:
        lowest_old = min(r["old_price"] for r in past)
        # Old price pushed up recently so the "discount" looks bigger.
        if deal.old_price > lowest_old * 1.10:
            return "old price inflated"
    return None


def collect(fetcher=None, stores=None):
    fetcher = fetcher or Fetcher()
    for key, cfg in config.STORES.items():
        if stores and key not in stores:
            continue
        try:
            yield from build(key, cfg).run(fetcher)
        except Exception:
            log.exception("Scraper for %s failed; continuing with other shops", cfg["name"])


def process(deals, conn):
    shown = hidden = 0
    for deal in deals:
        if not deal.category:
            deal.category = guess_category(deal.title)
        reason = check(deal, conn)
        db.upsert(conn, deal, reason)
        if reason:
            hidden += 1
            log.debug("Hidden (%s): %s", reason, deal.title)
        else:
            shown += 1
    expired = db.expire_stale(conn, config.EXPIRE_AFTER_HOURS)
    conn.commit()
    return {"shown": shown, "hidden": hidden, "expired": expired}


def export(conn, path=None):
    path = path or config.EXPORT_PATH
    rows = db.active_deals(conn)
    out = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(rows),
        "deals": [
            {
                "id": r["id"],
                "store": config.STORES.get(r["store"], {}).get("name", r["store"]),
                "title": r["title"],
                "category": r["category"],
                "price": r["price"],
                "old_price": r["old_price"],
                "discount_percent": (r["old_price"] - r["price"]) * 100 // r["old_price"],
                "image": r["image"],
                "promo_code": r["promo_code"] or None,
                "ends_at": r["ends_at"] or None,
                "first_seen": r["first_seen"],
                "link": affiliate.link_for(r["store"], r["url"]),
            }
            for r in rows
        ],
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


def run(stores=None, db_path=None, export_path=None, fetcher=None):
    conn = db.connect(db_path)
    stats = process(collect(fetcher, stores), conn)
    out = export(conn, export_path)
    stats["exported"] = out["count"]
    return stats
