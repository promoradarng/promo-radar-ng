"""Shops built on Magento (Slot, Kara and many other Nigerian retailers).

Magento listing pages share the same markup: <li class="product-item"> cards with
price boxes marked data-price-type="finalPrice" and "oldPrice".
"""

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import Scraper, parse_naira
from ..models import Deal


def _amount(box):
    if box is None:
        return 0
    if box.has_attr("data-price-amount"):
        try:
            return int(float(box["data-price-amount"]))
        except ValueError:
            pass
    return parse_naira(box.get_text())


class MagentoScraper(Scraper):
    def next_page_url(self, url, page):
        sep = "&" if "?" in url else "?"
        return url if page == 1 else f"{url}{sep}p={page}"

    def parse(self, html, page_url, category):
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("li.product-item, div.product-item"):
            link = card.select_one("a.product-item-link")
            final = card.select_one('[data-price-type="finalPrice"]')
            old = card.select_one('[data-price-type="oldPrice"]')
            if not (link and final and old):
                continue
            img = card.select_one("img.product-image-photo") or card.select_one("img")
            yield Deal(
                store=self.key,
                title=link.get_text(" ", strip=True),
                url=urljoin(self.cfg.get("base_url", page_url), link["href"]),
                price=_amount(final),
                old_price=_amount(old),
                category=category or "",
                image=(img.get("data-src") or img.get("src") or "") if img else "",
            )
