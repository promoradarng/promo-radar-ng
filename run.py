"""Find deals now.

    python run.py                 # all shops
    python run.py --store jumia   # one shop
"""

import argparse
import logging

from promo_radar import pipeline

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Promo Radar NG deal finder")
    ap.add_argument("--store", action="append", help="only run this shop (repeatable)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    stats = pipeline.run(stores=args.store)
    print(f"Listed {stats['shown']} deals, hid {stats['hidden']} (fake or too small), "
          f"expired {stats['expired']}. deals.json now has {stats['exported']} deals.")
