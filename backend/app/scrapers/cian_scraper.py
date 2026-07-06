"""CIAN scraper — uses cloudscraper to bypass Cloudflare WAF."""

import httpx
import asyncio
import json
import re
import logging
from typing import Optional
from app.scrapers.base import ScrapedItem

log = logging.getLogger("realty")

REGIONS = {
    "Москва": 1, "Санкт-Петербург": 2, "Новосибирск": 48,
    "Екатеринбург": 47, "Казань": 44, "Краснодар": 36,
    "Сочи": 37, "Владивосток": 75, "Самара": 51,
    "Уфа": 55, "Тюмень": 68, "Красноярск": 42,
    "Пермь": 50, "Воронеж": 38, "Ростов-на-Дону": 46,
}


class CianScraper:
    """
    CIAN scraper — uses cloudscraper to bypass Cloudflare.
    Falls back to httpx if cloudscraper unavailable.
    """
    SOURCE_NAME = "cian"
    BASE_URL = "https://www.cian.ru"
    API_URL = "https://api.cian.ru/search-offers/v2/search-offers-desktop/"

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.delay = 2.0

    def _get_scraper(self):
        """Create cloudscraper instance (imported lazily)."""
        try:
            import cloudscraper
            return cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "desktop": True}
            )
        except ImportError:
            log.warning("[cian] cloudscraper not installed, using httpx (may fail)")
            return None

    async def scrape_listings(
        self,
        city: str,
        deal_type: str = "sale",
        max_pages: int = 5,
        property_type: str = "apartment",
    ) -> list[ScrapedItem]:
        """Scrape CIAN via internal search API."""
        region_id = REGIONS.get(city, 1)
        scraper = self._get_scraper()

        if scraper is None:
            return await self._scrape_html_fallback(city, deal_type, max_pages)

        items = []
        for page in range(1, max_pages + 1):
            payload = {
                "jsonQuery": {
                    "region": {"type": "terms", "value": [region_id]},
                    "deal_type": {"type": "term", "value": deal_type},
                    "offer_type": {"type": "term", "value": "flat"},
                    "room": {"type": "terms", "value": []},
                    "sort": {"type": "term", "value": "creation_date_desc"},
                    "page": {"type": "term", "value": page},
                }
            }

            if property_type == "studio":
                payload["jsonQuery"]["room"] = {"type": "terms", "value": [0]}

            try:
                await asyncio.sleep(self.delay)
                # cloudscraper is sync, run in executor
                loop = asyncio.get_event_loop()
                resp = await loop.run_in_executor(
                    None,
                    lambda: scraper.post(self.API_URL, json=payload, timeout=30),
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                log.warning(f"[cian] Error page {page} for {city}: {e}")
                break

            offers = data.get("data", {}).get("offersSerialized", [])
            if not offers:
                break

            for offer in offers:
                item = self._parse_offer(offer, city, deal_type)
                if item:
                    items.append(item)

            log.info(f"[cian] {city}: page {page}, got {len(offers)} offers")

        log.info(f"[cian] {city} total: {len(items)} items")
        return items

    def _parse_offer(self, offer: dict, city: str, deal_type: str) -> Optional[ScrapedItem]:
        """Parse CIAN offer JSON."""
        try:
            offer_id = str(offer.get("id", ""))
            bargain = offer.get("bargainTerms", {})
            price = bargain.get("price") or offer.get("fullPrice", 0)
            if not price:
                return None

            geo = offer.get("geo", {})
            address_parts = []
            district = ""
            for addr in geo.get("address", []):
                if addr.get("title"):
                    address_parts.append(addr["title"])
                if addr.get("type") == "district":
                    district = addr["title"]
            address = ", ".join(address_parts)

            coords = geo.get("coordinates", {})
            metro_info = geo.get("metro", {})
            photos = offer.get("photos", [])
            images = [p.get("url2", p.get("url", "")) for p in photos[:10] if p.get("url")]

            rooms = offer.get("roomsCount")
            if rooms is None:
                title = offer.get("title", "").lower()
                if "студия" in title:
                    rooms = 0

            return ScrapedItem(
                source=self.SOURCE_NAME,
                source_id=offer_id,
                source_url=f"{self.BASE_URL}/sale/flat/{offer_id}/" if deal_type == "sale" else f"{self.BASE_URL}/rent/flat/{offer_id}/",
                property_type="apartment",
                deal_type=deal_type,
                price=float(price),
                address=address,
                city=city,
                district=district,
                lat=coords.get("lat"),
                lon=coords.get("lng"),
                area_m2=float(offer.get("totalArea")) if offer.get("totalArea") else None,
                rooms=rooms,
                floor=offer.get("floorNumber"),
                floors_total=offer.get("building", {}).get("floorsCount"),
                title=offer.get("title", ""),
                description=offer.get("description", ""),
                images=images,
            )
        except Exception as e:
            log.debug(f"[cian] Parse error: {e}")
            return None

    async def _scrape_html_fallback(self, city: str, deal_type: str, max_pages: int) -> list[ScrapedItem]:
        """Fallback: parse HTML pages with httpx (may fail due to WAF)."""
        from app.scrapers.base import BaseScraper

        items = []
        city_slug = {
            "Москва": "moskva", "Санкт-Петербург": "sankt-peterburg",
        }.get(city, "moskva")

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for page in range(1, max_pages + 1):
                if deal_type == "rent":
                    url = f"{self.BASE_URL}/snyat-kvartiru/{city_slug}/?p={page}"
                else:
                    url = f"{self.BASE_URL}/prodazha-kvartiry/{city_slug}/?p={page}"

                try:
                    await asyncio.sleep(self.delay)
                    resp = await client.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept-Language": "ru-RU,ru;q=0.9",
                    })
                    resp.raise_for_status()
                except Exception as e:
                    log.warning(f"[cian] HTML fallback failed: {e}")
                    break

                # Try JSON from HTML
                match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
                if match:
                    try:
                        next_data = json.loads(match.group(1))
                        offers = self._find_offers(next_data)
                        for offer in offers:
                            item = self._parse_offer(offer, city, deal_type)
                            if item:
                                items.append(item)
                    except json.JSONDecodeError:
                        pass

        return items

    def _find_offers(self, data: dict, depth: int = 0) -> list:
        """Find offers in nested JSON."""
        if depth > 5:
            return []
        if isinstance(data, list) and data and isinstance(data[0], dict) and "id" in data[0]:
            return data
        if isinstance(data, dict):
            for key in ["offersSerialized", "offers", "items", "results"]:
                if key in data:
                    if isinstance(data[key], list):
                        return data[key]
                    elif isinstance(data[key], dict):
                        result = self._find_offers(data[key], depth + 1)
                        if result:
                            return result
            for val in data.values():
                if isinstance(val, (dict, list)):
                    result = self._find_offers(val, depth + 1)
                    if result:
                        return result
        return []

    async def close(self):
        pass  # cloudscraper doesn't need explicit close
