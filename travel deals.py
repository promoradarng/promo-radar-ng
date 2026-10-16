"""
Promo Radar NG - automatic travel deals.

Runs after run.py in the "Find deals" workflow. It asks the Travelpayouts
(Aviasales) price feed for the cheapest recent fares on a few routes that
matter to Nigerians at home and in the UK, and adds them to docs/deals.json
under the "Travel" category.

- Needs the GitHub secret TRAVELPAYOUTS_TOKEN (never put the token in a file).
- Uses only Python's built-in libraries, so requirements.txt doesn't change.
- If anything goes wrong it keeps the previous travel deals and exits quietly,
  so it can never break your normal shop deals.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

DEALS_FILE = "docs/deals.json"

# Your Travelpayouts partner ID (marker). Taken from your Travelpayouts
# script on the homepage. Can be overridden with a TRAVELPAYOUTS_MARKER secret.
MARKER = os.environ.get("TRAVELPAYOUTS_MARKER", "").strip() or "585767"

# Routes to check: (from code, to code, from name, to name)
# LON = all London airports.
ROUTES = [
    ("LOS", "LON", "Lagos", "London"),
    ("ABV", "LON", "Abuja", "London"),
    ("LON", "LOS", "London", "Lagos"),
    ("LON", "ABV", "London", "Abuja"),
    ("LOS", "DXB", "Lagos", "Dubai"),
    ("LOS", "ACC", "Lagos", "Accra"),
    ("LOS", "ABV", "Lagos", "Abuja"),
    ("LOS", "PHC", "Lagos", "Port Harcourt"),
]

API = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


def log(msg):
    print(f"[travel] {msg}", flush=True)


def fetch_cheapest(token, origin, dest):
    params = {
        "origin": origin,
        "destination": dest,
        "currency": "ngn",
        "sorting": "price",
        "one_way": "true",
        "limit": "5",
        "market": "ng",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "X-Access-Token": token,
        "Accept": "application/json",
        "User-Agent": "promo-radar-ng",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    if not data.get("success", True):
        raise RuntimeError(data.get("error") or "API said no")
    return data.get("data") or []


def booking_link(item, origin, dest, dep):
    path = item.get("link") or ""
    if path:
        url = "https://www.aviasales.com" + (path if path.startswith("/") else "/" + path)
    else:
        url = f"https://www.aviasales.com/search/{origin}{dep:%d%m}{dest}1"
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}marker={MARKER}"


def parse_date(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def build_deal(item, origin, dest, from_name, to_name):
    price = item.get("price") or item.get("value")
    dep = parse_date(item.get("departure_at"))
    if not price or not dep:
        return None
    # Skip flights leaving in less than 2 days, they rarely still have that price.
    if dep < datetime.now(timezone.utc) + timedelta(days=2):
        return None
    stops = item.get("transfers")
    if stops == 0:
        stop_txt = "direct"
    elif isinstance(stops, int):
        stop_txt = f"{stops} stop" + ("" if stops == 1 else "s")
    else:
        stop_txt = ""
    title = f"{from_name} to {to_name} one-way flight, {dep:%d %b}"
    if stop_txt:
        title += f" ({stop_txt})"
    price = int(round(float(price)))
    return {
        "id": f"travel-{origin}-{dest}".lower(),
        "title": title,
        "category": "Travel",
        "store": "Aviasales",
        "price": price,
        # No "was" price for flights, so the site shows no fake discount.
        "old_price": price,
        "promo_code": None,
        "link": booking_link(item, origin, dest, dep),
        "image": "",
        "ends_at": None,
    }


def main():
    token = os.environ.get("TRAVELPAYOUTS_TOKEN", "").strip()
    if not token:
        log("No TRAVELPAYOUTS_TOKEN secret found. Skipping travel deals.")
        return 0

    try:
        with open(DEALS_FILE, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception as e:
        log(f"Could not read {DEALS_FILE} ({e}). Skipping.")
        return 0
    if isinstance(doc, list):
        doc = {"deals": doc}
    deals = doc.get("deals") or []

    new_travel = []
    for origin, dest, from_name, to_name in ROUTES:
        try:
            items = fetch_cheapest(token, origin, dest)
        except Exception as e:
            log(f"{origin}-{dest}: no data ({e})")
            continue
        for item in items:
            deal = build_deal(item, origin, dest, from_name, to_name)
            if deal:
                new_travel.append(deal)
                log(f"{origin}-{dest}: NGN {deal['price']:,} on {item.get('departure_at')}")
                break
        else:
            log(f"{origin}-{dest}: no usable fares")

    if not new_travel:
        log("No travel fares found this run. Keeping previous travel deals.")
        return 0

    kept = [d for d in deals if not str(d.get("id", "")).startswith("travel-")]
    doc["deals"] = kept + new_travel
    with open(DEALS_FILE, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    log(f"Added {len(new_travel)} travel deals.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # never break the main deal finder
        log(f"Unexpected problem: {e}")
        sys.exit(0)
