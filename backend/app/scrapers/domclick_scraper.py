"""DomClick scraper — uses public research API (no proxy needed)."""

import httpx
import asyncio
import logging
from typing import Optional
from app.scrapers.base import BaseScraper, ScrapedItem

log = logging.getLogger("realty")

# DomClick uses geo coordinates for search
CITY_COORDS = {
    "Москва": {"lat": 55.75, "lon": 37.62, "radius": 20000},
    "Санкт-Петербург": {"lat": 59.93, "lon": 30.32, "radius": 15000},
    "Новосибирск": {"lat": 55.03, "lon": 82.92, "radius": 12000},
    "Екатеринбург": {"lat": 56.84, "lon": 60.60, "radius": 12000},
    "Казань": {"lat": 55.79, "lon": 49.12, "radius": 12000},
    "Краснодар": {"lat": 45.04, "lon": 38.98, "radius": 12000},
    "Сочи": {"lat": 43.60, "lon": 39.73, "radius": 15000},
    "Владивосток": {"lat": 43.12, "lon": 131.89, "radius": 12000},
    "Самара": {"lat": 53.20, "lon": 50.15, "radius": 12000},
    "Уфа": {"lat": 54.74, "lon": 55.97, "radius": 12000},
    "Тюмень": {"lat": 57.15, "lon": 65.53, "radius": 12000},
    "Красноярск": {"lat": 56.01, "lon": 92.87, "radius": 12000},
    "Пермь": {"lat": 58.01, "lon": 56.25, "radius": 12000},
    "Воронеж": {"lat": 51.67, "lon": 39.18, "radius": 12000},
    "Ростов-на-Дону": {"lat": 47.24, "lon": 39.71, "radius": 12000},
}


class DomClickScraper(BaseScraper):
    """
    DomClick scraper — uses their public research API.
    Most reliable: returns structured JSON, no proxy needed.
    """
    SOURCE_NAME = "domclick"
    BASE_URL = "https://domclick.ru"
    API_URL = "https://api.domclick.ru/research/v5/offers"

    def __init__(self, proxy: Optional[str] = None):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "ru-RU,ru;q=0.9",
                "Origin": "https://domclick.ru",
                "Referer": "https://domclick.ru/",
            },
        )
        self.delay = 1.5
        self.proxy = proxy

    async def scrape_listings(
        self,
        city: str,
        deal_type: str = "sale",
        max_pages: int = 5,
        property_type: str = "apartment",
    ) -> list[ScrapedItem]:
        """Scrape DomClick via public API."""
        coords = CITY_COORDS.get(city, CITY_COORDS["Москва"])
        limit_per_page = 25
        items = []

        for page in range(max_pages):
            offset = page * limit_per_page
            params = {
                "deal_type": deal_type,
                "category": property_type,
                "address": str({"lat": coords["lat"], "lng": coords["lon"], "radius": coords["radius"]}).replace("'", '"'),
                "offset": offset,
                "limit": limit_per_page,
                "sort": "date_desc",
            }

            try:
                await asyncio.sleep(self.delay)
                resp = await self.client.get(self.API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                log.warning(f"[domclick] HTTP {e.response.status_code} for {city} page {page}")
                break
            except Exception as e:
                log.warning(f"[domclick] Error for {city} page {page}: {e}")
                break

            offers = data.get("result", {}).get("offers", [])
            if not offers:
                break

            for offer in offers:
                item = self._parse_offer(offer, city, deal_type)
                if item:
                    items.append(item)

            log.info(f"[domclick] {city}: page {page+1}, got {len(offers)} offers")

        log.info(f"[domclick] {city} total: {len(items)} items")
        return items

    def _parse_offer(self, offer: dict, city: str, deal_type: str) -> Optional[ScrapedItem]:
        """Parse DomClick offer JSON."""
        try:
            offer_id = str(offer.get("id", ""))
            price_data = offer.get("price", {})
            price = price_data.get("value", 0)
            if not price:
                return None

            addr = offer.get("address", {})
            address = addr.get("full", "")
            district = addr.get("district", "")

            geo = offer.get("geo", {})
            lat = geo.get("lat")
            lon = geo.get("lon")

            area = offer.get("totalArea")
            area_living = offer.get("livingArea")
            area_kitchen = offer.get("kitchenArea")
            rooms = offer.get("rooms")
            floor = offer.get("floor")
            floors_total = offer.get("floorsTotal")

            building = offer.get("building", {})
            year = building.get("buildYear")
            wall_type = building.get("wallType", "")

            photos = offer.get("photos", [])
            images = [p.get("url", "") for p in photos[:10] if p.get("url")]

            metro = offer.get("metro", {})
            metro_station = metro.get("name", "")
            metro_minutes = metro.get("time")

            title = offer.get("title", "")
            description = offer.get("description", "")

            return ScrapedItem(
                source=self.SOURCE_NAME,
                source_id=offer_id,
                source_url=f"https://domclick.ru/offers/{offer_id}",
                property_type="apartment",
                deal_type=deal_type,
                price=float(price),
                address=address,
                city=city,
                district=district,
                lat=lat,
                lon=lon,
                area_m2=float(area) if area else None,
                rooms=rooms,
                floor=floor,
                floors_total=floors_total,
                description=description or title,
                images=images,
                features={
                    "year": year,
                    "wall_type": wall_type,
                    "area_living": float(area_living) if area_living else None,
                    "area_kitchen": float(area_kitchen) if area_kitchen else None,
                },
            )
        except Exception as e:
            log.debug(f"[domclick] Parse error: {e}")
            return None

    async def close(self):
        await self.client.aclose()
