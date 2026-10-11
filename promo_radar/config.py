"""Settings for Promo Radar NG. Edit this file to add shops, categories and affiliate IDs."""

import os

# Where the database lives, and where the deals file for the website is written.
# The website in docs/ reads docs/deals.json, and GitHub Pages serves the docs/ folder.
ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR = os.environ.get("PROMO_RADAR_DATA", os.path.join(ROOT, "data"))
DB_PATH = os.path.join(DATA_DIR, "deals.db")
EXPORT_PATH = os.environ.get("PROMO_RADAR_EXPORT", os.path.join(ROOT, "docs", "deals.json"))

# Be polite to shop servers: wait between page requests and identify ourselves.
REQUEST_DELAY_SECONDS = 4
# Shops ask bots to say who they are and who runs them.
BOT_NAME = "PromoRadarNG"
USER_AGENT = "PromoRadarNG/0.2 (deals finder; +https://promoradarng.github.io/promo-radar-ng/)"
TIMEOUT_SECONDS = 20

# A deal must be at least this many percent off to be listed.
MIN_DISCOUNT_PERCENT = 10
# Hide a deal if the shop raised the "old price" in the last N days (classic fake-discount trick).
FAKE_DISCOUNT_LOOKBACK_DAYS = 30
# Remove deals we have not seen again within this many hours.
EXPIRE_AFTER_HOURS = 24

# Affiliate settings. Fill these in after you are approved by each programme.
# Leave a value empty and the app will link straight to the shop without tracking.
AFFILIATE = {
    "jumia": os.environ.get("JUMIA_AFFILIATE_ID", ""),
    "konga": os.environ.get("KONGA_AFFILIATE_ID", ""),
    "slot": os.environ.get("SLOT_AFFILIATE_ID", ""),
    "kara": os.environ.get("KARA_AFFILIATE_ID", ""),
}

# Pages on each shop that list products. The finder keeps only items with an old price.
# Use plain category pages: Jumia's robots.txt forbids sorted (?sort=) and filtered pages.
# Check these URLs in a browser from time to time: shops rename pages.
STORES = {
    "jumia": {
        "name": "Jumia",
        "scraper": "jumia",
        "pages": [
            ("https://www.jumia.com.ng/flash-sales/", None),
            ("https://www.jumia.com.ng/phones-tablets/", "Phones"),
            ("https://www.jumia.com.ng/electronics/", "Electronics"),
            ("https://www.jumia.com.ng/home-office/", "Home & Kitchen"),
            ("https://www.jumia.com.ng/groceries/", "Groceries"),
            ("https://www.jumia.com.ng/category-fashion-by-jumia/", "Fashion"),
            ("https://www.jumia.com.ng/health-beauty/", "Beauty & Health"),
        ],
        "max_pages_per_url": 2,
    },
    "slot": {
        "name": "Slot",
        "scraper": "magento",
        "base_url": "https://slot.ng",
        "pages": [
            ("https://slot.ng/mobile-phones.html", "Phones"),
            ("https://slot.ng/laptops.html", "Electronics"),
        ],
        "max_pages_per_url": 2,
    },
    # Kara's robots.txt does not allow automated visitors, so it is switched off.
    # Ask Kara for a product feed or a partnership instead.
}

# Shops and marketplaces that must never be listed.
BLOCKED_DOMAINS = {
    "tiktok.com", "temu.com", "alibaba.com", "aliexpress.com", "shein.com",
}

# Keyword rules for putting a product in a category when the page doesn't say.
CATEGORY_KEYWORDS = {
    "Phones": ["phone", "smartphone", "tecno", "infinix", "itel", "iphone", "galaxy", "redmi", "tablet"],
    "Electronics": ["tv", "television", "laptop", "earbud", "headphone", "speaker", "power bank", "freepods", "monitor", "camera"],
    "Home & Kitchen": ["freezer", "fridge", "refrigerator", "blender", "kettle", "air conditioner", " ac", "fan", "microwave", "cooker", "iron"],
    "Groceries": ["rice", "oil", "spaghetti", "noodles", "milo", "sugar", "flour", "beverage", "cereal"],
    "Fashion": ["shoe", "sneaker", "dress", "shirt", "kaftan", "bag", "watch", "jeans", "ankara"],
    "Beauty & Health": ["lotion", "perfume", "cream", "toothbrush", "monitor", "vitamin", "shampoo", "hair"],
}
