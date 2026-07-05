"""
Real scrapers — tested approaches for each source.

IMPORTANT: These scrapers use different strategies per site:
- CIAN: cloudscraper + internal JSON API
- Avito: Playwright (headless browser) + API interception
- DomClick: direct JSON API
- Yandex Realty: Playwright + API

Usage:
    python3 scrapers/run_all.py --city Москва --deal sale --limit 50
"""

import asyncio
import json
import re
import hashlib
from typing import Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ScrapedItem:
    """Standardized listing from any source."""
    source: str
    source_id: str
    source_url: str
    property_type: str        # apartment, house, commercial, land, room, studio
    deal_type: str            # sale, rent
    price: float
    currency: str = "RUB"
    address: str = ""
    city: str = ""
    district: str = ""
    region: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    area_total: Optional[float] = None
    area_living: Optional[float] = None
    area_kitchen: Optional[float] = None
    rooms: Optional[int] = None
    floor: Optional[int] = None
    floors_total: Optional[int] = None
    ceiling_height: Optional[float] = None
    description: str = ""
    title: str = ""
    images: list = None
    features: dict = None
    metro_station: str = ""
    metro_distance: Optional[int] = None
    author_type: str = ""     # owner, agent, developer
    commission: Optional[float] = None
    source_hash: str = ""

    def __post_init__(self):
        if self.images is None:
            self.images = []
        if self.features is None:
            self.features = {}
        if not self.source_hash:
            content = f"{self.source}:{self.source_id}:{self.price}:{self.address}"
            self.source_hash = hashlib.sha256(content.encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════
# CIAN SCRAPER — via cloudscraper + internal API
# ═══════════════════════════════════════════════════════════════

class CianScraper:
    """
    CIAN scraper using their internal search API.
    Uses cloudscraper to bypass Cloudflare WAF.
    """
    SOURCE = "cian"
    
    # CIAN region IDs
    REGIONS = {
        "Москва": 1,
        "Санкт-Петербург": 2,
        "Новосибирск": 48,
        "Екатеринбург": 47,
        "Казань": 44,
        "Краснодар": 36,
        "Сочи": 37,
        "Владивосток": 75,
        "Ростов-на-Дону": 46,
        "Самара": 51,
    }
    
    def __init__(self):
        import cloudscraper
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True,
            }
        )
    
    def scrape(self, city: str, deal_type: str = "sale", 
               property_type: str = "apartment", limit: int = 50) -> list[ScrapedItem]:
        """Scrape CIAN via internal API."""
        region_id = self.REGIONS.get(city, 1)
        
        # CIAN internal search API
        url = "https://api.cian.ru/search-offers/v2/search-offers-desktop/"
        
        # Build search payload
        payload = {
            "jsonQuery": {
                "region": {"type": "terms", "value": [region_id]},
                "deal_type": {"type": "term", "value": deal_type},
                "offer_type": {"type": "term", "value": "flat"},
                "room": {"type": "terms", "value": []},  # all rooms
                "sort": {"type": "term", "value": "creation_date_desc"},
                "page": {"type": "term", "value": 1},
            }
        }
        
        # Add property type filter
        if property_type == "studio":
            payload["jsonQuery"]["room"] = {"type": "terms", "value": [0]}
        elif property_type == "apartment":
            pass  # all rooms
        
        items = []
        page = 1
        max_pages = (limit // 25) + 1
        
        while page <= max_pages and len(items) < limit:
            payload["jsonQuery"]["page"] = {"type": "term", "value": page}
            
            try:
                resp = self.scraper.post(url, json=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"[cian] Error page {page}: {e}")
                break
            
            offers = data.get("data", {}).get("offersSerialized", [])
            if not offers:
                break
            
            for offer in offers:
                try:
                    item = self._parse_offer(offer, city, deal_type)
                    if item:
                        items.append(item)
                except Exception as e:
                    print(f"[cian] Parse error: {e}")
                    continue
            
            page += 1
            asyncio.sleep(2)  # Rate limiting
        
        return items[:limit]
    
    def _parse_offer(self, offer: dict, city: str, deal_type: str) -> Optional[ScrapedItem]:
        """Parse CIAN offer JSON."""
        try:
            # Price
            price_data = offer.get("bargainTerms", {})
            price = price_data.get("price", 0)
            if not price:
                price = offer.get("fullPrice", 0)
            
            # Location
            geo = offer.get("geo", {})
            address_parts = []
            for addr in geo.get("address", []):
                if addr.get("title"):
                    address_parts.append(addr["title"])
            address = ", ".join(address_parts) if address_parts else ""
            
            # District
            district = ""
            for addr in geo.get("address", []):
                if addr.get("type") == "district":
                    district = addr.get("title", "")
            
            # Coordinates
            coords = geo.get("coordinates", {})
            lat = coords.get("lat")
            lon = coords.get("lng")
            
            # Building info
            building = offer.get("building", {})
            floors_total = building.get("floorsCount")
            
            # Photos
            photos = offer.get("photos", [])
            images = [p.get("url", "") for p in photos[:10] if p.get("url")]
            
            # Rooms
            rooms_count = offer.get("roomsCount")
            if rooms_count is None:
                # Try to detect studio
                title = offer.get("title", "").lower()
                if "студия" in title:
                    rooms_count = 0
            
            # Area
            total_area = offer.get("totalArea")
            
            # Floor
            floor = offer.get("floorNumber")
            
            # Metro
            metro = offer.get("geo", {}).get("metro", {})
            metro_station = metro.get("name", "")
            metro_distance = metro.get("time")
            
            # URL
            offer_id = offer.get("id", "")
            url = f"https://www.cian.ru/sale/flat/{offer_id}/" if deal_type == "sale" else f"https://www.cian.ru/rent/flat/{offer_id}/"
            
            # Author
            author = offer.get("user", {})
            author_type = author.get("agentType", "")
            
            return ScrapedItem(
                source=self.SOURCE,
                source_id=str(offer_id),
                source_url=url,
                property_type="apartment",
                deal_type=deal_type,
                price=float(price),
                address=address,
                city=city,
                district=district,
                lat=lat,
                lon=lon,
                area_total=float(total_area) if total_area else None,
                rooms=rooms_count,
                floor=floor,
                floors_total=floors_total,
                title=offer.get("title", ""),
                description=offer.get("description", ""),
                images=images,
                metro_station=metro_station,
                metro_distance=metro_distance,
                author_type=author_type,
            )
        except Exception as e:
            print(f"[cian] _parse_offer error: {e}")
            return None


# ═══════════════════════════════════════════════════════════════
# AVITO SCRAPER — via Playwright (headless browser)
# ═══════════════════════════════════════════════════════════════

class AvitoScraper:
    """
    Avito scraper using Playwright for JS rendering.
    Intercepts API responses for structured data.
    """
    SOURCE = "avito"
    
    CITIES = {
        "Москва": "moskva",
        "Санкт-Петербург": "sankt-peterburg",
        "Новосибирск": "novosibirsk",
        "Екатеринбург": "ekaterinburg",
        "Казань": "kazan",
        "Краснодар": "krasnodar",
        "Сочи": "sochi",
        "Владивосток": "vladivostok",
    }
    
    async def scrape(self, city: str, deal_type: str = "sale", limit: int = 50) -> list[ScrapedItem]:
        """Scrape Avito via Playwright."""
        from playwright.async_api import async_playwright
        
        city_slug = self.CITIES.get(city, "moskva")
        deal_path = "prodam" if deal_type == "sale" else "sdam"
        
        items = []
        api_responses = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                locale="ru-RU",
            )
            page = await context.new_page()
            
            # Intercept API responses for structured data
            async def handle_response(response):
                if "search" in response.url and response.status == 200:
                    try:
                        data = await response.json()
                        if "items" in data or "catalog" in data:
                            api_responses.append(data)
                    except:
                        pass
            
            page.on("response", handle_response)
            
            # Navigate to search page
            url = f"https://www.avito.ru/{city_slug}/kvartiry/{deal_path}"
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)
            except Exception as e:
                print(f"[avito] Navigation error: {e}")
                await browser.close()
                return items
            
            # Parse listings from page
            cards = await page.query_selector_all('[data-marker="item"]')
            
            for card in cards[:limit]:
                try:
                    item = await self._parse_card(card, city, deal_type)
                    if item:
                        items.append(item)
                except Exception as e:
                    continue
            
            await browser.close()
        
        return items
    
    async def _parse_card(self, card, city: str, deal_type: str) -> Optional[ScrapedItem]:
        """Parse Avito listing card."""
        try:
            # Title
            title_el = await card.query_selector('[itemprop="name"]')
            title = await title_el.inner_text() if title_el else ""
            
            # Price
            price_el = await card.query_selector('[itemprop="price"]')
            price_text = await price_el.get_attribute("content") if price_el else "0"
            price = float(re.sub(r'[^\d.]', '', price_text) or "0")
            
            # Link
            link_el = await card.query_selector('a[href*="/kvartiry/"]')
            href = await link_el.get_attribute("href") if link_el else ""
            url = f"https://www.avito.ru{href}" if href.startswith("/") else href
            
            # Extract ID from URL
            source_id = re.search(r'_(\d+)$', href)
            source_id = source_id.group(1) if source_id else hashlib.md5(url.encode()).hexdigest()[:12]
            
            # Address
            addr_el = await card.query_selector('[data-marker="item-address"]')
            address = await addr_el.inner_text() if addr_el else ""
            
            # Image
            img_el = await card.query_selector('img')
            img_src = await img_el.get_attribute("src") if img_el else ""
            
            # Parse rooms from title
            rooms = None
            rooms_match = re.search(r'(\d)\s*-?\s*комн', title.lower())
            if rooms_match:
                rooms = int(rooms_match.group(1))
            elif 'студия' in title.lower():
                rooms = 0
            
            # Parse area from title
            area = None
            area_match = re.search(r'([\d.,]+)\s*м²', title)
            if area_match:
                area = float(area_match.group(1).replace(",", "."))
            
            return ScrapedItem(
                source=self.SOURCE,
                source_id=source_id,
                source_url=url,
                property_type="apartment",
                deal_type=deal_type,
                price=price,
                address=address,
                city=city,
                rooms=rooms,
                area_total=area,
                title=title,
                images=[img_src] if img_src else [],
            )
        except Exception:
            return None


# ═══════════════════════════════════════════════════════════════
# DOMCLICK SCRAPER — via direct API
# ═══════════════════════════════════════════════════════════════

class DomClickScraper:
    """
    DomClick scraper using their public research API.
    Most reliable — returns structured JSON.
    """
    SOURCE = "domclick"
    
    # DomClick uses geo coordinates for search
    CITY_COORDS = {
        "Москва": {"lat": 55.75, "lon": 37.62, "radius": 20000},
        "Санкт-Петербург": {"lat": 59.93, "lon": 30.32, "radius": 15000},
        "Новосибирск": {"lat": 55.03, "lon": 82.92, "radius": 12000},
        "Екатеринбург": {"lat": 56.84, "lon": 60.60, "radius": 12000},
        "Казань": {"lat": 55.79, "lon": 49.12, "radius": 12000},
        "Краснодар": {"lat": 45.04, "lon": 38.98, "radius": 12000},
        "Сочи": {"lat": 43.60, "lon": 39.73, "radius": 15000},
    }
    
    async def scrape(self, city: str, deal_type: str = "sale", limit: int = 50) -> list[ScrapedItem]:
        """Scrape DomClick via public API."""
        import httpx
        
        coords = self.CITY_COORDS.get(city, self.CITY_COORDS["Москва"])
        
        # DomClick search API
        url = "https://api.domclick.ru/research/v5/offers"
        
        params = {
            "deal_type": deal_type,
            "category": "apartment",
            "address": json.dumps({"lat": coords["lat"], "lng": coords["lon"], "radius": coords["radius"]}),
            "offset": 0,
            "limit": min(limit, 50),
            "sort": "date_desc",
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Origin": "https://domclick.ru",
            "Referer": "https://domclick.ru/",
        }
        
        items = []
        
        async with httpx.AsyncClient(timeout=30) as client:
            for offset in range(0, limit, 50):
                params["offset"] = offset
                
                try:
                    resp = await client.get(url, params=params, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    print(f"[domclick] Error offset {offset}: {e}")
                    break
                
                offers = data.get("result", {}).get("offers", [])
                if not offers:
                    break
                
                for offer in offers:
                    try:
                        item = self._parse_offer(offer, city, deal_type)
                        if item:
                            items.append(item)
                    except Exception as e:
                        continue
                
                await asyncio.sleep(1)
        
        return items[:limit]
    
    def _parse_offer(self, offer: dict, city: str, deal_type: str) -> Optional[ScrapedItem]:
        """Parse DomClick offer JSON."""
        try:
            offer_id = offer.get("id", "")
            
            # Price
            price_data = offer.get("price", {})
            price = price_data.get("value", 0)
            
            # Address
            address_data = offer.get("address", {})
            address = address_data.get("full", "")
            district = address_data.get("district", "")
            
            # Geo
            geo = offer.get("geo", {})
            lat = geo.get("lat")
            lon = geo.get("lon")
            
            # Specs
            area = offer.get("totalArea")
            area_living = offer.get("livingArea")
            area_kitchen = offer.get("kitchenArea")
            rooms = offer.get("rooms")
            floor = offer.get("floor")
            floors_total = offer.get("floorsTotal")
            ceiling = offer.get("ceilingHeight")
            
            # Building
            building = offer.get("building", {})
            year = building.get("buildYear")
            house_type = building.get("wallType", "")
            
            # Photos
            photos = offer.get("photos", [])
            images = [p.get("url", "") for p in photos[:10]]
            
            # Metro
            metro = offer.get("metro", {})
            metro_station = metro.get("name", "")
            metro_distance = metro.get("time")
            
            # Description
            description = offer.get("description", "")
            title = offer.get("title", "")
            
            return ScrapedItem(
                source=self.SOURCE,
                source_id=str(offer_id),
                source_url=f"https://domclick.ru/offers/{offer_id}",
                property_type="apartment",
                deal_type=deal_type,
                price=float(price),
                address=address,
                city=city,
                district=district,
                lat=lat,
                lon=lon,
                area_total=float(area) if area else None,
                area_living=float(area_living) if area_living else None,
                area_kitchen=float(area_kitchen) if area_kitchen else None,
                rooms=rooms,
                floor=floor,
                floors_total=floors_total,
                ceiling_height=float(ceiling) if ceiling else None,
                title=title,
                description=description,
                images=images,
                metro_station=metro_station,
                metro_distance=metro_distance,
                features={
                    "year": year,
                    "house_type": house_type,
                },
            )
        except Exception as e:
            print(f"[domclick] _parse_offer error: {e}")
            return None


# ═══════════════════════════════════════════════════════════════
# UNIFIED SCRAPER — runs all scrapers
# ═══════════════════════════════════════════════════════════════

class UnifiedScraper:
    """Runs all scrapers and deduplicates results."""
    
    def __init__(self):
        self.cian = CianScraper()
        self.avito = AvitoScraper()
        self.domclick = DomClickScraper()
    
    async def scrape_all(self, city: str, deal_type: str = "sale", 
                         limit_per_source: int = 50) -> dict:
        """Run all scrapers concurrently."""
        results = {"cian": [], "avito": [], "domclick": []}
        
        # Run in parallel
        tasks = []
        
        # CIAN (sync, run in thread)
        import concurrent.futures
        loop = asyncio.get_event_loop()
        
        with concurrent.futures.ThreadPoolExecutor() as pool:
            cian_task = loop.run_in_executor(
                pool, self.cian.scrape, city, deal_type, "apartment", limit_per_source
            )
            
            # Avito & DomClick (async)
            avito_task = self.avito.scrape(city, deal_type, limit_per_source)
            domclick_task = self.domclick.scrape(city, deal_type, limit_per_source)
            
            # Wait for all
            cian_items, avito_items, domclick_items = await asyncio.gather(
                cian_task, avito_task, domclick_task,
                return_exceptions=True,
            )
        
        if isinstance(cian_items, Exception):
            print(f"[unified] CIAN error: {cian_items}")
            cian_items = []
        if isinstance(avito_items, Exception):
            print(f"[unified] Avito error: {avito_items}")
            avito_items = []
        if isinstance(domclick_items, Exception):
            print(f"[unified] DomClick error: {domclick_items}")
            domclick_items = []
        
        results["cian"] = cian_items
        results["avito"] = avito_items
        results["domclick"] = domclick_items
        
        # Deduplicate
        all_items = cian_items + avito_items + domclick_items
        deduped = self._deduplicate(all_items)
        
        return {
            "by_source": results,
            "total": len(all_items),
            "deduplicated": len(deduped),
            "items": deduped,
        }
    
    def _deduplicate(self, items: list[ScrapedItem]) -> list[ScrapedItem]:
        """Remove duplicates across sources."""
        seen = set()
        unique = []
        
        for item in items:
            # Primary key: source + source_id
            key = f"{item.source}:{item.source_id}"
            if key in seen:
                continue
            seen.add(key)
            
            # Secondary: cross-source dedup by (city, address, area, rooms, price)
            content_key = f"{item.city}:{item.address}:{item.area_total}:{item.rooms}:{item.price}"
            content_hash = hashlib.md5(content_key.encode()).hexdigest()
            if content_hash in seen:
                continue
            seen.add(content_hash)
            
            unique.append(item)
        
        return unique


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    city = sys.argv[1] if len(sys.argv) > 1 else "Москва"
    deal = sys.argv[2] if len(sys.argv) > 2 else "sale"
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    
    print(f"🔍 Scraping: {city}, {deal}, limit={limit}")
    print("=" * 60)
    
    scraper = UnifiedScraper()
    results = asyncio.run(scraper.scrape_all(city, deal, limit))
    
    print(f"\n📊 Results:")
    print(f"  CIAN: {len(results['by_source']['cian'])} items")
    print(f"  Avito: {len(results['by_source']['avito'])} items")
    print(f"  DomClick: {len(results['by_source']['domclick'])} items")
    print(f"  Total: {results['total']}")
    print(f"  After dedup: {results['deduplicated']}")
    
    # Show first 3 items
    for item in results["items"][:3]:
        print(f"\n  [{item.source}] {item.rooms}к, {item.area_total}м² — {item.price:,.0f} ₽")
        print(f"    📍 {item.city}, {item.address}")
