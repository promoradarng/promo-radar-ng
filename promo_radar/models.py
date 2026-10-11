from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib


@dataclass
class Deal:
    store: str            # store key, e.g. "jumia"
    title: str
    url: str              # product page on the shop's own site
    price: int            # current price in Naira
    old_price: int        # price before discount in Naira
    category: str = "Other"
    image: str = ""
    promo_code: str = ""
    ends_at: str = ""     # ISO timestamp if the shop shows one
    seen_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    @property
    def id(self) -> str:
        return hashlib.sha1(f"{self.store}|{self.url}".encode()).hexdigest()[:16]

    @property
    def discount_percent(self) -> int:
        if not self.old_price or self.old_price <= self.price:
            return 0
        # Round down so we never overstate a discount (16.6% shows as 16%, not 17%).
        return (self.old_price - self.price) * 100 // self.old_price
