# Promo Radar NG - travel deals with pictures. Adds cheap fares to docs/deals.json.
import base64, json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
F = "docs/deals.json"
MARKER = os.environ.get("TRAVELPAYOUTS_MARKER", "").strip() or "585767"
ROUTES = [("LOS", "LON", "Lagos", "London"), ("ABV", "LON", "Abuja", "London"),
          ("LON", "LOS", "London", "Lagos"), ("LON", "ABV", "London", "Abuja"),
          ("LOS", "DXB", "Lagos", "Dubai"), ("LOS", "ACC", "Lagos", "Accra"),
          ("LOS", "ABV", "Lagos", "Abuja"), ("LOS", "PHC", "Lagos", "Port Harcourt")]
SKY = {"LON": ("#2f5d8a", "#8fb4d9"), "LOS": ("#0f7a4a", "#7fd1a6"), "ABV": ("#1d6b5a", "#9fd3b8"),
       "DXB": ("#b8641d", "#f3c06b"), "ACC": ("#a9412c", "#f0a07a"), "PHC": ("#2d6c8f", "#8ccbe0")}

def log(m): print("[travel] " + m, flush=True)

def art(o, d, a, b):
    top, bot = SKY.get(d, ("#2f5d8a", "#8fb4d9"))
    x, bars = 0, ""
    for i, h in enumerate([70, 110, 85, 140, 60, 120, 95, 150, 75, 105, 65, 125, 90]):
        w = 26 + (i * 7) % 12
        bars += f'<rect x="{x}" y="{400 - h}" width="{w}" height="{h}" rx="2"/>'
        x += w + 4
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
           f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bot}"/></linearGradient></defs>'
           f'<rect width="400" height="400" fill="url(#g)"/><circle cx="335" cy="165" r="30" fill="#fff" opacity=".25"/>'
           '<path d="M40 250 Q200 120 360 200" fill="none" stroke="#fff" stroke-width="3" stroke-dasharray="2 10" stroke-linecap="round" opacity=".8"/>'
           '<g transform="translate(250 150) rotate(15)" fill="#fff"><path d="M-38 -4 L22 -4 Q38 -4 42 0 Q38 4 22 4 L-38 4 Q-42 0 -38 -4Z"/>'
           '<path d="M-2 -3 L-20 -34 L-10 -34 L16 -3Z"/><path d="M-2 3 L-20 34 L-10 34 L16 3Z"/>'
           '<path d="M-34 -3 L-42 -16 L-36 -16 L-26 -3Z"/><path d="M-34 3 L-42 16 L-36 16 L-26 3Z"/></g>'
           f'<g fill="#000" opacity=".22">{bars}</g>'
           f'<text x="32" y="70" font-family="Arial" font-size="52" font-weight="700" fill="#fff">{o} → {d}</text>'
           f'<text x="32" y="108" font-family="Arial" font-size="24" fill="#fff">{a} to {b}</text>'
           '<text x="32" y="372" font-family="Arial" font-size="20" font-weight="700" fill="#fff">✈ FLIGHT DEAL</text></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()

def fares(token, o, d):
    q = urllib.parse.urlencode({"origin": o, "destination": d, "currency": "ngn", "sorting": "price",
                                "one_way": "true", "limit": "5", "market": "ng"})
    req = urllib.request.Request("https://api.travelpayouts.com/aviasales/v3/prices_for_dates?" + q,
                                 headers={"X-Access-Token": token, "User-Agent": "promo-radar-ng"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r).get("data") or []

def deal(it, o, d, a, b):
    try: dep = datetime.fromisoformat(str(it.get("departure_at")).replace("Z", "+00:00"))
    except ValueError: return None
    price = it.get("price") or it.get("value")
    if not price or dep < datetime.now(timezone.utc) + timedelta(days=2): return None
    t = it.get("transfers")
    stop = "direct" if t == 0 else (f"{t} stop" + ("" if t == 1 else "s") if isinstance(t, int) else "")
    path = it.get("link") or f"/search/{o}{dep:%d%m}{d}1"
    link = "https://www.aviasales.com" + ("" if path.startswith("/") else "/") + path
    link += ("&" if "?" in link else "?") + "marker=" + MARKER
    title = f"{a} to {b} one-way flight, {dep:%d %b}" + (f" ({stop})" if stop else "")
    return {"id": f"travel-{o}-{d}".lower(), "title": title, "category": "Travel", "store": "Aviasales",
            "price": int(round(float(price))), "old_price": int(round(float(price))), "promo_code": None,
            "link": link, "image": art(o, d, a, b), "ends_at": None}

try:
    token = os.environ.get("TRAVELPAYOUTS_TOKEN", "").strip()
    if not token:
        log("No TRAVELPAYOUTS_TOKEN secret. Skipping."); sys.exit(0)
    doc = json.load(open(F, encoding="utf-8"))
    new = []
    for o, d, a, b in ROUTES:
        try:
            found = next((x for x in (deal(i, o, d, a, b) for i in fares(token, o, d)) if x), None)
        except Exception as e:
            log(f"{o}-{d}: no data ({str(e)[:80]})"); continue
        if found:
            new.append(found); log(f"{o}-{d}: NGN {found['price']:,}")
    if new:
        doc["deals"] = [x for x in doc["deals"] if not str(x.get("id", "")).startswith("travel-")] + new
        if "count" in doc: doc["count"] = len(doc["deals"])
        json.dump(doc, open(F, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        log(f"Added {len(new)} travel deals.")
    else:
        log("No fares found this run. Keeping previous travel deals.")
except SystemExit:
    raise
except Exception as e:
    log("Problem: " + str(e)[:200])
sys.exit(0)
