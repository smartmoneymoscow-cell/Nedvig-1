"""Unified scraper runner — orchestrates all scrapers."""

import asyncio
import logging
from typing import Optional
from app.scrapers.domclick_scraper import DomClickScraper
from app.scrapers.cian_scraper import CianScraper
from app.scrapers.avito_scraper import AvitoScraper
from app.scrapers.n1_scraper import N1Scraper
from app.scrapers.base import ScrapedItem

log = logging.getLogger("realty")


class ScraperRunner:
    """Runs all scrapers in parallel and deduplicates results."""

    def __init__(self, proxies: Optional[list[str]] = None):
        self.proxies = proxies or []
        self._proxy_idx = 0

    def _get_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        proxy = self.proxies[self._proxy_idx % len(self.proxies)]
        self._proxy_idx += 1
        return proxy

    async def scrape_city(
        self,
        city: str,
        deal_type: str = "sale",
        sources: Optional[list[str]] = None,
        max_pages: int = 3,
    ) -> dict:
        """
        Scrape a city from all (or specified) sources in parallel.
        
        Returns:
            {
                "city": str,
                "deal_type": str,
                "by_source": {"domclick": [...], "cian": [...], ...},
                "total_raw": int,
                "total_deduped": int,
                "items": [ScrapedItem, ...],
            }
        """
        available_scrapers = {
            "domclick": lambda: DomClickScraper(proxy=self._get_proxy()),
            "cian": lambda: CianScraper(proxy=self._get_proxy()),
            "avito": lambda: AvitoScraper(proxy=self._get_proxy()),
            "n1": lambda: N1Scraper(proxy=self._get_proxy()),
        }

        active_sources = sources or list(available_scrapers.keys())
        scrapers = {name: available_scrapers[name]() for name in active_sources if name in available_scrapers}

        # Run all scrapers in parallel
        tasks = {}
        for name, scraper in scrapers.items():
            tasks[name] = asyncio.create_task(
                self._safe_scrape(scraper, name, city, deal_type, max_pages)
            )

        results = {}
        for name, task in tasks.items():
            results[name] = await task

        # Collect all items
        all_items = []
        for name, items in results.items():
            all_items.extend(items)

        # Deduplicate by (city, address, price, rooms)
        deduped = self._deduplicate(all_items)

        return {
            "city": city,
            "deal_type": deal_type,
            "by_source": {name: len(items) for name, items in results.items()},
            "total_raw": len(all_items),
            "total_deduped": len(deduped),
            "items": deduped,
        }

    async def scrape_all_cities(
        self,
        cities: list[str],
        deal_type: str = "sale",
        sources: Optional[list[str]] = None,
        max_pages: int = 2,
    ) -> dict:
        """Scrape multiple cities."""
        all_items = []
        city_results = {}

        for city in cities:
            log.info(f"═══ Scraping {city} ({deal_type}) ═══")
            result = await self.scrape_city(city, deal_type, sources, max_pages)
            city_results[city] = {
                "by_source": result["by_source"],
                "total": result["total_deduped"],
            }
            all_items.extend(result["items"])
            # Delay between cities to be respectful
            await asyncio.sleep(5)

        return {
            "cities": city_results,
            "total_items": len(all_items),
            "items": all_items,
        }

    async def _safe_scrape(
        self, scraper, name: str, city: str, deal_type: str, max_pages: int
    ) -> list[ScrapedItem]:
        """Run a scraper with error handling."""
        try:
            items = await scraper.scrape_listings(city, deal_type, max_pages)
            return items
        except Exception as e:
            log.error(f"[{name}] Scraper failed for {city}: {e}")
            return []
        finally:
            try:
                await scraper.close()
            except Exception:
                pass

    def _deduplicate(self, items: list[ScrapedItem]) -> list[ScrapedItem]:
        """Remove duplicates by source+id and content hash."""
        seen_keys = set()
        seen_content = set()
        unique = []

        for item in items:
            # Primary: source + source_id
            key = f"{item.source}:{item.source_id}"
            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Secondary: content hash (city + address + price + rooms)
            content = f"{item.city}:{item.address}:{item.price}:{item.rooms}:{item.area_m2}"
            import hashlib
            content_hash = hashlib.md5(content.encode()).hexdigest()
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)

            unique.append(item)

        return unique
