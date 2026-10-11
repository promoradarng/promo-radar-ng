import os
import sqlite3
from datetime import datetime, timedelta, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS deals (
    id TEXT PRIMARY KEY,
    store TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    category TEXT,
    image TEXT,
    price INTEGER NOT NULL,
    old_price INTEGER NOT NULL,
    promo_code TEXT,
    ends_at TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    hidden_reason TEXT
);
CREATE TABLE IF NOT EXISTS price_history (
    deal_id TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    price INTEGER NOT NULL,
    old_price INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_hist ON price_history(deal_id, seen_at);
CREATE TABLE IF NOT EXISTS clicks (
    deal_id TEXT NOT NULL,
    clicked_at TEXT NOT NULL
);
"""


def connect(path=None):
    path = path or config.DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert(conn, deal, hidden_reason=None):
    now = deal.seen_at
    conn.execute(
        """INSERT INTO deals (id, store, title, url, category, image, price, old_price,
                              promo_code, ends_at, first_seen, last_seen, active, hidden_reason)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             title=excluded.title, category=excluded.category, image=excluded.image,
             price=excluded.price, old_price=excluded.old_price,
             promo_code=excluded.promo_code, ends_at=excluded.ends_at,
             last_seen=excluded.last_seen, active=excluded.active,
             hidden_reason=excluded.hidden_reason""",
        (deal.id, deal.store, deal.title, deal.url, deal.category, deal.image,
         deal.price, deal.old_price, deal.promo_code, deal.ends_at, now, now,
         0 if hidden_reason else 1, hidden_reason),
    )
    conn.execute(
        "INSERT INTO price_history (deal_id, seen_at, price, old_price) VALUES (?,?,?,?)",
        (deal.id, now, deal.price, deal.old_price),
    )


def history(conn, deal_id, days):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    return conn.execute(
        "SELECT seen_at, price, old_price FROM price_history WHERE deal_id=? AND seen_at>=? ORDER BY seen_at",
        (deal_id, since),
    ).fetchall()


def expire_stale(conn, hours):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
    cur = conn.execute(
        "UPDATE deals SET active=0, hidden_reason='expired' WHERE active=1 AND last_seen < ?", (cutoff,)
    )
    return cur.rowcount


def active_deals(conn):
    return conn.execute(
        "SELECT * FROM deals WHERE active=1 ORDER BY (1.0 - price*1.0/old_price) DESC"
    ).fetchall()
