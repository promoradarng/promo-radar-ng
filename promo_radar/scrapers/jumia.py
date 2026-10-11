"""Jumia Nigeria listing pages. Product cards are <article class="prd"> elements."""

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import Scraper, parse_naira
from ..models import Deal


class JumiaScraper(Scraper):
    BASE = "https://www.jumia.com.ng"

    def parse(self, html, page_url, category):
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("article.prd"):
            link = card.select_one("a.core") or card.select_one("a[href]")
            name = card.select_one(".name")
            price = card.select_one(".prc")
            old = card.select_one(".old")
            if not (link and name and price and old):
                continue  # no old price means no discount
            img = card.select_one("img")
            yield Deal(
                store=self.key,
                title=name.get_text(" ", strip=True),
                url=urljoin(self.BASE, link["href"].split("?")[0]),
                price=parse_naira(price.get_text()),
                old_price=parse_naira(old.get_text()),
                category=category or "",
                image=(img.get("data-src") or img.get("src") or "") if img else "",
            )
