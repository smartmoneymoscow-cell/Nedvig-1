#!/usr/bin/env python3
"""
CLI script to run scrapers.

Usage:
    python scripts/scrape.py --city Москва --source domclick --limit 3
    python scripts/scrape.py --city all --source all --deal sale
    python scripts/scrape.py --test  # quick test all scrapers
"""

import asyncio
import argparse
import json
import logging
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.scrapers.runner import ScraperRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("scrape")

ALL_CITIES = [
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург",
    "Казань", "Краснодар", "Сочи", "Владивосток",
]

ALL_SOURCES = ["domclick", "cian", "avito", "n1"]


async def test_scrapers():
    """Quick test: run each scraper for 1 page on Moscow."""
    runner = ScraperRunner()
    city = "Москва"

    for source in ALL_SOURCES:
        log.info(f"\n{'='*50}")
        log.info(f"Testing: {source}")
        log.info(f"{'='*50}")
        try:
            result = await runner.scrape_city(
                city, deal_type="sale", sources=[source], max_pages=1
            )
            items = result["items"]
            if items:
                log.info(f"✅ {source}: {len(items)} items")
                for item in items[:3]:
                    log.info(f"   {item.rooms}к, {item.area_m2}м² — {item.price:,.0f} ₽ — {item.address[:50]}")
            else:
                log.warning(f"⚠️ {source}: 0 items (blocked or empty)")
        except Exception as e:
            log.error(f"❌ {source}: {e}")


async def run_scrape(city: str, source: str, deal: str, max_pages: int, output: str):
    """Run scraping and optionally save results."""
    runner = ScraperRunner()

    sources = ALL_SOURCES if source == "all" else [source]
    cities = ALL_CITIES if city == "all" else [city]

    if len(cities) == 1:
        result = await runner.scrape_city(cities[0], deal, sources, max_pages)
        items = result["items"]
        log.info(f"\n{'='*50}")
        log.info(f"Results for {cities[0]} ({deal}):")
        log.info(f"  Sources: {result['by_source']}")
        log.info(f"  Total raw: {result['total_raw']}")
        log.info(f"  After dedup: {result['total_deduped']}")
    else:
        result = await runner.scrape_all_cities(cities, deal, sources, max_pages)
        items = result["items"]
        log.info(f"\n{'='*50}")
        log.info(f"Total across {len(cities)} cities: {result['total_items']} items")
        for city_name, city_data in result["cities"].items():
            log.info(f"  {city_name}: {city_data['total']} items ({city_data['by_source']})")

    # Show first 10 items
    log.info(f"\nFirst {min(10, len(items))} items:")
    for i, item in enumerate(items[:10], 1):
        price_str = f"{item.price:,.0f} ₽".replace(",", " ")
        rooms_str = f"{item.rooms}к" if item.rooms is not None else "—"
        log.info(f"  {i}. [{item.source}] {rooms_str}, {item.area_m2 or '—'}м² — {price_str}")
        log.info(f"     📍 {item.city}, {item.address[:60]}")

    # Save to JSON if output specified
    if output:
        data = [
            {
                "source": item.source,
                "source_id": item.source_id,
                "source_url": item.source_url,
                "property_type": item.property_type,
                "deal_type": item.deal_type,
                "price": item.price,
                "address": item.address,
                "city": item.city,
                "rooms": item.rooms,
                "area_m2": item.area_m2,
                "floor": item.floor,
                "description": item.description[:200] if item.description else "",
            }
            for item in items
        ]
        with open(output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info(f"\n💾 Saved {len(data)} items to {output}")


def main():
    parser = argparse.ArgumentParser(description="Run real estate scrapers")
    parser.add_argument("--city", default="Москва", help="City name or 'all'")
    parser.add_argument("--source", default="domclick", help="Source name or 'all'")
    parser.add_argument("--deal", default="sale", choices=["sale", "rent"])
    parser.add_argument("--pages", type=int, default=3, help="Max pages per source")
    parser.add_argument("--output", "-o", help="Save results to JSON file")
    parser.add_argument("--test", action="store_true", help="Quick test all scrapers")
    args = parser.parse_args()

    if args.test:
        asyncio.run(test_scrapers())
    else:
        asyncio.run(run_scrape(args.city, args.source, args.deal, args.pages, args.output))


if __name__ == "__main__":
    main()
