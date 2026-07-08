"""Yandex Realty scraper — uses public search API."""

import httpx
import asyncio
import logging
from typing import Optional
from app.scrapers.base import BaseScraper, ScrapedItem

log = logging.getLogger("realty")

CITY_COORDS = {
    "Москва": {"lat": 55.75, "lon": 37.62},
    "Санкт-Петербург": {"lat": 59.93, "lon": 30.32},
    "Новосибирск": {"lat": 55.03, "lon": 82.92},
    "Екатеринбург": {"lat": 56.84, "lon": 60.60},
    "Казань": {"lat": 55.79, "lon": 49.12},
    "Краснодар": {"lat": 45.04, "lon": 38.98},
    "Сочи": {"lat": 43.60, "lon": 39.73},
}


class YandexRealtyScraper(BaseScraper):
    """Yandex Realty — parses search results."""
    SOURCE_NAME = "yandex"
    BASE_URL = "https://realty.ya.ru"

    async def scrape_listings(self, city: str, deal_type: str = "sale", max_pages: int = 3) -> list[ScrapedItem]:
        items = []
        try:
            coords = CITY_COORDS.get(city, CITY_COORDS["Москва"])
            category = "SELL" if deal_type == "sale" else "RENT"

            for page in range(1, max_pages + 1):
                url = "https://realty.ya.ru/api/search"
                params = {
                    "category": category,
                    "type": "APARTMENT",
                    "rgid": "0",
                    "lat": coords["lat"],
                    "lon": coords["lon"],
                    "page": page,
                    "pageSize": 20,
                }
                html = await self.fetch_page(url, params)
                if not html:
                    break
                # Parse would go here — Yandex requires JS rendering
                # Returning empty for now as their API requires auth
                break
        except Exception as e:
            log.warning(f"[yandex] Error scraping {city}: {e}")
        return items
