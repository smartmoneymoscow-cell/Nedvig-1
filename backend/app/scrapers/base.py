"""Base scraper class — all site scrapers inherit from this."""

import httpx
import asyncio
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
from selectolax.parser import HTMLParser
from app.config import get_settings

settings = get_settings()


class ScrapedItem:
    """Standardized item from any source."""
    def __init__(
        self,
        source: str,
        source_id: str,
        source_url: str,
        property_type: str,
        deal_type: str,
        price: float,
        address: str,
        city: str,
        **kwargs,
    ):
        self.source = source
        self.source_id = source_id
        self.source_url = source_url
        self.property_type = property_type
        self.deal_type = deal_type
        self.price = price
        self.address = address
        self.city = city
        self.currency = kwargs.get("currency", "RUB")
        self.area_m2 = kwargs.get("area_m2")
        self.rooms = kwargs.get("rooms")
        self.floor = kwargs.get("floor")
        self.floors_total = kwargs.get("floors_total")
        self.district = kwargs.get("district")
        self.region = kwargs.get("region")
        self.lat = kwargs.get("lat")
        self.lon = kwargs.get("lon")
        self.description = kwargs.get("description")
        self.images = kwargs.get("images", [])
        self.features = kwargs.get("features", {})

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


class BaseScraper(ABC):
    """Base class for site scrapers."""

    SOURCE_NAME: str = "unknown"
    BASE_URL: str = ""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            },
        )
        self.delay = settings.SCRAPE_DOWNLOAD_DELAY

    @abstractmethod
    async def scrape_listings(self, city: str, deal_type: str = "sale", max_pages: int = 5) -> list[ScrapedItem]:
        """Scrape listings from the source. Must be implemented by subclasses."""
        pass

    async def fetch_page(self, url: str, params: Optional[dict] = None) -> Optional[str]:
        """Fetch a page with rate limiting."""
        try:
            await asyncio.sleep(self.delay)
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"[{self.SOURCE_NAME}] Error fetching {url}: {e}")
            return None

    def parse_html(self, html: str) -> HTMLParser:
        return HTMLParser(html)

    async def close(self):
        await self.client.aclose()
