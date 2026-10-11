import re
import time
import logging
import urllib.robotparser
from urllib.parse import urlparse

import requests

from .. import config

log = logging.getLogger(__name__)


def parse_naira(text: str) -> int:
    """Turn '₦ 189,000' or 'NGN 1,250.50' into 189000 / 1250. Returns 0 if no number."""
    if not text:
        return 0
    # Price ranges like "₦ 5,000 - ₦ 7,000": take the first price.
    first = re.split(r"\s[-–]\s", text)[0]
    digits = re.sub(r"[^\d.]", "", first)
    if not digits:
        return 0
    try:
        return int(float(digits))
    except ValueError:
        return 0


class Fetcher:
    """Downloads pages politely: checks robots.txt, waits between requests."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = config.USER_AGENT
        self._robots = {}
        self._last = 0.0

    def allowed(self, url: str) -> bool:
        host = urlparse(url).netloc
        if any(host.endswith(b) for b in config.BLOCKED_DOMAINS):
            return False
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"https://{host}/robots.txt")
            try:
                rp.read()
            except Exception:
                rp = None  # robots.txt unreachable: proceed carefully
            self._robots[host] = rp
        rp = self._robots[host]
        return True if rp is None else rp.can_fetch(config.USER_AGENT, url)

    def get(self, url: str) -> str | None:
        if not self.allowed(url):
            log.warning("Skipping (blocked by robots.txt or block list): %s", url)
            return None
        wait = config.REQUEST_DELAY_SECONDS - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()
        try:
            r = self.session.get(url, timeout=config.TIMEOUT_SECONDS)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            log.warning("Could not fetch %s: %s", url, e)
            return None


class Scraper:
    """Each shop scraper turns a listing page's HTML into Deal objects."""

    def __init__(self, store_key: str, store_cfg: dict):
        self.key = store_key
        self.cfg = store_cfg

    def parse(self, html: str, page_url: str, category: str | None):
        raise NotImplementedError

    def next_page_url(self, url: str, page: int) -> str:
        sep = "&" if "?" in url else "?"
        return url if page == 1 else f"{url}{sep}page={page}"

    def run(self, fetcher: Fetcher):
        for url, category in self.cfg["pages"]:
            for page in range(1, self.cfg.get("max_pages_per_url", 1) + 1):
                page_url = self.next_page_url(url, page)
                html = fetcher.get(page_url)
                if not html:
                    break
                found = list(self.parse(html, page_url, category))
                log.info("%s: %d deals on %s", self.cfg["name"], len(found), page_url)
                if not found:
                    break
                yield from found
