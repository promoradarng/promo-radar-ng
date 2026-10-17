"""
Promo Radar NG - Slot deals (for Slot's new website, 2026).

Slot rebuilt slot.ng: products are loaded by the page after it opens, so a
simple download sees an empty page. This script opens Slot's category pages in
a real (headless) Chrome browser on GitHub, waits for the products, and adds
real discounts to docs/deals.json with store "Slot".

- Runs after run.py and travel_deals.py in the "Find deals" workflow.
- Only lists items that show an old price higher than the current price
  (a real discount between MIN_OFF% and MAX_OFF%).
- If anything goes wrong it keeps the previous Slot deals and exits quietly,
  so it can never break your normal deals.
- It also prints the data addresses Slot's pages use ("[slot] api:" lines),
  which helps us make it faster and more reliable later.
"""

import json
import os
import re
import sys

DEALS_FILE = "docs/deals.json"
MIN_OFF = 5      # ignore tiny discounts
MAX_OFF = 70     # bigger "discounts" are usually a fake old price
MAX_PER_CATEGORY = 40

# (page on slot.ng, category on Promo Radar)
PAGES = [
    ("https://slot.ng/category/phones-and-tablets", "Phones"),
    ("https://slot.ng/category/laptops", "Electronics"),
    ("https://slot.ng/category/appliances", "Home & Kitchen"),
    ("https://slot.ng/category/watches", "Electronics"),
    ("https://slot.ng/category/Home-And-Audio-Speakers", "Electronics"),
    ("https://slot.ng/category/generators-power-solutions", "Home & Kitchen"),
]

NAME_KEYS = ("name", "title", "product_name", "productName")
NOW_KEYS = ("sale_price", "salePrice", "discount_price", "discountPrice", "discounted_price",
            "special_price", "specialPrice", "selling_price", "sellingPrice", "offer_price",
            "promo_price", "current_price", "final_price", "price")
WAS_KEYS = ("old_price", "oldPrice", "regular_price", "regularPrice", "original_price",
            "originalPrice", "compare_at_price", "compareAtPrice", "market_price", "list_price",
            "listPrice", "slashed_price", "before_price", "retail_price", "price")
IMG_KEYS = ("image", "image_url", "imageUrl", "thumbnail", "featured_image", "cover", "photo", "images")


def log(msg):
    print(f"[slot] {msg}", flush=True)


def num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = re.sub(r"[^\d.]", "", v)
        try:
            return float(s) if s else None
        except ValueError:
            return None
    if isinstance(v, dict):  # e.g. {"amount": 1000}
        for k in ("amount", "value", "price"):
            if k in v:
                return num(v[k])
    return None


def first_image(d):
    for k in IMG_KEYS:
        v = d.get(k)
        if isinstance(v, list) and v:
            v = v[0]
        if isinstance(v, dict):
            v = v.get("url") or v.get("src") or v.get("path")
        if isinstance(v, str) and v:
            if v.startswith("http"):
                return v
            return "https://api-prod.slot.ng/" + v.lstrip("/")
    return ""


def product_from_dict(d):
    """Turn one JSON object into (name, now, was, slug, image) if it looks like a product."""
    name = next((d[k] for k in NAME_KEYS if isinstance(d.get(k), str) and d[k].strip()), None)
    if not name:
        return None
    prices = {k: num(d.get(k)) for k in set(NOW_KEYS + WAS_KEYS) if k in d}
    prices = {k: v for k, v in prices.items() if v and v > 100}
    if len(set(prices.values())) < 2:
        return None
    now = min(prices.values())
    was = max(prices.values())
    slug = d.get("slug") or d.get("url_key") or d.get("handle") or ""
    if not isinstance(slug, str):
        slug = ""
    return name.strip(), now, was, slug.strip("/"), first_image(d)


def walk(obj, out):
    if isinstance(obj, dict):
        p = product_from_dict(obj)
        if p:
            out.append(p)
        for v in obj.values():
            walk(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, out)


NAIRA = re.compile(r"₦\s?([\d,]+(?:\.\d+)?)")


def products_from_cards(cards):
    """Fallback: read product cards from the rendered page (text + link + image)."""
    out = []
    for c in cards:
        amounts = [float(a.replace(",", "")) for a in NAIRA.findall(c.get("text", ""))]
        amounts = [a for a in amounts if a > 100]
        if len(set(amounts)) < 2:
            continue
        lines = [l.strip() for l in c.get("text", "").splitlines() if l.strip()]
        name = next((l for l in lines if "₦" not in l and not l.endswith("%") and len(l) > 6), None)
        href = c.get("href", "")
        m = re.search(r"/products/([^/?#]+)", href)
        if not name or not m:
            continue
        out.append((name, min(amounts), max(amounts), m.group(1), c.get("img", "")))
    return out


def to_deal(p, category):
    name, now, was, slug, img = p
    if not slug:
        return None
    off = (was - now) * 100 / was
    if off < MIN_OFF or off > MAX_OFF:
        return None
    return {
        "id": "slot-" + slug.lower(),
        "title": name,
        "category": category,
        "store": "Slot",
        "price": int(round(now)),
        "old_price": int(round(was)),
        "promo_code": None,
        "link": "https://slot.ng/products/" + slug,
        "image": img,
        "ends_at": None,
    }


def scrape():
    from playwright.sync_api import sync_playwright

    found = {}
    api_seen = set()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
            locale="en-NG",
        )
        for url, category in PAGES:
            payloads = []

            def on_response(resp):
                try:
                    ctype = resp.headers.get("content-type", "")
                    if "json" in ctype and "slot.ng" in resp.url:
                        payloads.append(resp.json())
                        short = resp.url.split("?")[0]
                        if short not in api_seen:
                            api_seen.add(short)
                            log(f"api: {resp.url[:180]}")
                except Exception:
                    pass

            page = ctx.new_page()
            page.on("response", on_response)
            try:
                page.goto(url, wait_until="networkidle", timeout=45000)
                for _ in range(4):  # scroll to load more products
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(1200)
                cards = page.eval_on_selector_all(
                    "a[href*='/products/']",
                    """els => els.map(a => {
                        const card = a.closest('div') || a;
                        const box = card.parentElement || card;
                        const img = box.querySelector('img');
                        return {href: a.href, text: box.innerText || '', img: img ? (img.currentSrc || img.src) : ''};
                    })""",
                )
            except Exception as e:
                log(f"{url}: could not load ({e.__class__.__name__}: {str(e)[:120]})")
                page.close()
                continue
            page.close()

            items = []
            for pl in payloads:
                walk(pl, items)
            source = "data"
            if not items:
                items = products_from_cards(cards)
                source = "page"
            n = 0
            for p in items:
                d = to_deal(p, category)
                if d and d["id"] not in found:
                    found[d["id"]] = d
                    n += 1
                    if n >= MAX_PER_CATEGORY:
                        break
            log(f"{url}: {len(cards)} product links, {len(items)} priced items ({source}), {n} real deals")
        browser.close()
    return list(found.values())


def main():
    try:
        with open(DEALS_FILE, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception as e:
        log
