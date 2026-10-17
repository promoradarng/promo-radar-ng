# Promo Radar NG - Slot deals. Adds real Slot discounts to docs/deals.json.
import json, re, sys
F = "docs/deals.json"
PAGES = [("phones-and-tablets", "Phones"), ("laptops", "Electronics"),
         ("appliances", "Home & Kitchen"), ("watches", "Electronics"),
         ("Home-And-Audio-Speakers", "Electronics"), ("generators-power-solutions", "Home & Kitchen")]
PK = ["price", "sale_price", "salePrice", "discount_price", "discountPrice", "special_price",
      "selling_price", "old_price", "oldPrice", "regular_price", "original_price", "market_price", "list_price"]

def log(m): print("[slot] " + m, flush=True)

def num(v):
    try: return float(re.sub(r"[^\d.]", "", str(v)) or 0)
    except ValueError: return 0

def img(d, depth=0):
    for v in (d.values() if isinstance(d, dict) else d):
        if isinstance(v, str) and re.search(r"\.(webp|jpe?g|png)(\?|$)", v, re.I):
            return v if v.startswith("http") else "https://api-prod.slot.ng/storage/" + v.lstrip("/").removeprefix("storage/")
        if isinstance(v, (dict, list)) and depth < 2:
            f = img(v, depth + 1)
            if f: return f
    return ""

def walk(o, out):
    if isinstance(o, dict):
        p = [num(o[k]) for k in PK if k in o and not isinstance(o[k], (dict, list))]
        p = [x for x in p if x > 100]
        n = o.get("name") or o.get("title")
        if isinstance(n, str) and o.get("slug") and "shop all" not in n.lower() and len(set(p)) > 1:
            out.append((n, min(p), max(p), str(o["slug"]), img(o)))
        for v in o.values(): walk(v, out)
    elif isinstance(o, list):
        for v in o: walk(v, out)

def cards(cs):
    out = []
    for c in cs:
        a = [float(x.replace(",", "")) for x in re.findall(r"₦\s?([\d,]+)", c["t"])]
        a = [x for x in a if x > 100]
        s = re.search(r"/products/([^/?#]+)", c["h"])
        n = next((l.strip() for l in c["t"].split("\n") if len(l.strip()) > 6 and "₦" not in l), "")
        if s and n and len(set(a)) > 1:
            out.append((n, min(a), max(a), s.group(1), c["i"]))
    return out

def scrape():
    from playwright.sync_api import sync_playwright
    found = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0 Safari/537.36")
        for slug, cat in PAGES:
            url, data = "https://slot.ng/category/" + slug, []
            pg = ctx.new_page()
            def got(r):
                try:
                    if "json" in r.headers.get("content-type", "") and "slot.ng" in r.url:
                        data.append(r.json()); log("api: " + r.url[:150])
                except Exception: pass
            pg.on("response", got)
            try:
                pg.goto(url, wait_until="networkidle", timeout=45000)
                for _ in range(4): pg.mouse.wheel(0, 4000); pg.wait_for_timeout(1200)
                cs = pg.eval_on_selector_all("a[href*='/products/']", """e => e.map(a => {
                    const b = (a.closest('div') || a).parentElement || a; const i = b.querySelector('img');
                    return {h: a.href, t: b.innerText || '', i: i ? i.src : ''}; })""")
            except Exception as e:
                log(url + " could not load: " + str(e)[:100]); pg.close(); continue
            pg.close()
            items = []
            for d in data: walk(d, items)
            if not items: items = cards(cs)
            n = 0
            for name, now, was, s, im in items:
                off = (was - now) * 100 / was
                if 5 <= off <= 70 and "slot-" + s not in found and n < 40:
                    found["slot-" + s] = {"id": "slot-" + s.lower(), "title": name, "category": cat,
                        "store": "Slot", "price": int(now), "old_price": int(was), "promo_code": None,
                        "link": "https://slot.ng/products/" + s, "image": im, "ends_at": None}
                    n += 1
            log(f"{url}: {len(cs)} links, {len(items)} priced, {n} deals")
        b.close()
    return list(found.values())

try:
    doc = json.load(open(F, encoding="utf-8"))
    new = scrape()
    if new:
        doc["deals"] = [d for d in doc["deals"] if not str(d.get("id", "")).startswith("slot-")] + new
        if "count" in doc: doc["count"] = len(doc["deals"])
        json.dump(doc, open(F, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        log(f"Added {len(new)} Slot deals.")
    else:
        log("No Slot discounts found this run.")
except Exception as e:
    log("Problem: " + str(e)[:200])
sys.exit(0)
