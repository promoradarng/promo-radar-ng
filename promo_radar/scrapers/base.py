import re
import time
import logging
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


class RobotsRules:
    """Reads a robots.txt file, including the * and $ wildcards most shops use.

    Python's built-in robots reader ignores wildcards, so it gets rules like
    "Disallow: /*sort=" wrong. This one follows Google's documented behaviour:
    the longest matching rule wins, and Allow wins a tie.
    """

    def __init__(self, text: str, agent_token: str):
        self.rules = self._pick_group(text, agent_token.lower())

    @staticmethod
    def _pick_group(text, token):
        groups, agents, rules, last_was_agent = [], [], [], False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (p.strip() for p in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if not last_was_agent and agents:
                    groups.append((agents, rules))
                    agents, rules = [], []
                agents.append(value.lower())
                last_was_agent = True
            elif key in ("allow", "disallow"):
                last_was_agent = False
                if value:
                    rules.append((key == "allow", value))
        if agents:
            groups.append((agents, rules))
        specific = [r for a, r in groups if any(x != "*" and x in token for x in a)]
        if specific:
            return [rule for r in specific for rule in r]
        return [rule for a, r in groups if "*" in a for rule in r]

    @staticmethod
    def _to_regex(pattern):
        anchored = pattern.endswith("$")
        body = re.escape(pattern.rstrip("$")).replace(r"\*", ".*")
        return re.compile(body + ("$" if anchored else ""))

    def allows(self, url: str) -> bool:
        parts = urlparse(url)
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        best_len, best_allow = -1, True
        for allow, pattern in self.rules:
            if self._to_regex(pattern).match(path):
                if len(pattern) > best_len or (len(pattern) == best_len and allow):
                    best_len, best_allow = len(pattern), allow
        return best_allow


class Fetcher:
    """Downloads pages politely: follows robots.txt, waits between requests,
    and never tries to get around a shop that blocks automated visitors."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = config.USER_AGENT
        self._robots = {}
        self._last = 0.0

    def _wait(self):
        wait = config.REQUEST_DELAY_SECONDS - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def _robots_for(self, host):
        """Returns RobotsRules, "open" (no robots.txt), or a reason string to skip the shop."""
        if host in self._robots:
            return self._robots[host]
        self._wait()
        try:
            r = self.session.get(f"https://{host}/robots.txt", timeout=config.TIMEOUT_SECONDS)
            if r.status_code == 200:
                result = RobotsRules(r.text, config.BOT_NAME)
            elif r.status_code == 404:
                result = "open"
            elif r.status_code in (401, 403, 429):
                result = f"the shop refused our visit (HTTP {r.status_code}); it blocks automated visitors"
            else:
                result = f"robots.txt returned HTTP {r.status_code}"
        except requests.RequestException as e:
            result = f"could not reach the shop ({e.__class__.__name__})"
        self._robots[host] = result
        if isinstance(result, str) and result != "open":
            log.warning("%s: skipping this shop because %s", host, result)
        return result

    def get(self, url: str) -> str | None:
        host = urlparse(url).netloc
        if any(host.endswith(b) for b in config.BLOCKED_DOMAINS):
            log.warning("Skipping blocked marketplace: %s", url)
            return None
        robots = self._robots_for(host)
        if isinstance(robots, str) and robots != "open":
            return None
        if isinstance(robots, RobotsRules) and not robots.allows(url):
            log.warning("Skipping (the shop's robots.txt does not allow this page): %s", url)
            return None
        self._wait()
        try:
            r = self.session.get(url, timeout=config.TIMEOUT_SECONDS)
            if r.status_code in (401, 403, 429):
                log.warning("Skipping (the shop refused the visit, HTTP %s): %s", r.status_code, url)
                return None
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
