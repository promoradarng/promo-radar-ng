from .jumia import JumiaScraper
from .magento import MagentoScraper

SCRAPERS = {
    "jumia": JumiaScraper,
    "magento": MagentoScraper,
}


def build(store_key, store_cfg):
    return SCRAPERS[store_cfg["scraper"]](store_key, store_cfg)
