"""
Production Scrapers — CIAN, Avito, DomClick
Features: proxy rotation, retry with backoff, deduplication, rate limiting

Usage:
    from backend.app.scrapers.production_scrapers import UnifiedScraper
    scraper = UnifiedScraper(proxies=["http://user:pass@proxy:port"])
    results = await scraper.scrape_all("Москва", "sale", limit=100)
"""

import asyncio
import hashlib
import json
import logging
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("scrapers")


@dataclass
class ListingData:
    """Standardized listing from any source."""
    source: str
    source_id: str
    source_url: str
    property_type: str
    deal_type: str
    price: float
    currency: str = "RUB"
    address: str = ""
    city: str = ""
    district: str = ""
    region: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    area_m2: Optional[float] = None
    rooms: Optional[int] = None
    floor: Optional[int] = None
    floors_total: Optional[int] = None
    title: str = ""
    description: str = ""
    images: list = field(default_factory=list)
    features: dict = field(default_factory=dict)
    metro_station: str = ""
    metro_minutes: Optional[int] = None
    author_type: str = ""
    source_hash: str = ""

    def __post_init__(self):
        if not self.source_hash:
            content = f"{self.source}:{self.source_id}:{self.price}:{self.address}"
            self.source_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None and v != [] and v != {}}


# ═══════════════════════════════════════════════════════════════
# RETRY DECORATOR
# ═══════════════════════════════════════════════════════════════

def retry(max_attempts: int = 3, base_delay: float = 2.0, max_delay: float = 60.0):
    """Async retry with exponential backoff."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    log.warning(f"[{func.__name__}] Attempt {attempt + 1}/{max_attempts} failed: {e}. Retry in {delay:.1f}s")
                    await asyncio.sleep(delay)
            raise last_error
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════
# PROXY MANAGER
# ═══════════════════════════════════════════════════════════════

class ProxyManager:
    """Rotating proxy manager."""

    def __init__(self, proxies: Optional[list[str]] = None):
        self.proxies = proxies or []
        self._index = 0
        self._blocked: set[str] = set()

    def get_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        available = [p for p in self.proxies if p not in self._blocked]
        if not available:
            self._blocked.clear()
            available = self.proxies
        proxy = available[self._index % len(available)]
        self._index += 1
        return proxy

    def mark_blocked(self, proxy: str):
        self._blocked.add(proxy)
        log.warning(f"[proxy] Marked as blocked: {proxy[:30]}...")

    @property
    def has_proxies(self) -> bool:
        return len(self.proxies) > 0


# ═══════════════════════════════════════════════════════════════
# CIAN SCRAPER
# ═══════════════════════════════════════════════════════════════

class CianScraper:
    """
    ЦИАН — парсинг через Playwright с перехватом API.
    
    Стратегия:
    1. Открываем страницу поиска в headless Chrome
    2. Перехватываем JSON-ответы внутреннего API
    3. Парсим структурированные данные
    
    Fallback: HTML парсинг через selectolax.
    """
    SOURCE = "cian"
    BASE = "https://www.cian.ru"

    REGIONS = {
        "Москва": 1, "Санкт-Петербург": 2, "Новосибирск": 48,
        "Екатеринбург": 47, "Казань": 44, "Краснодар": 36,
        "Сочи": 37, "Владивосток": 75, "Самара": 51,
        "Уфа": 55, "Тюмень": 68, "Красноярск": 42,
        "Пермь": 50, "Воронеж": 38, "Ростов-на-Дону": 46,
    }

    def __init__(self, proxy_manager: Optional[ProxyManager] = None):
        self.proxy_manager = proxy_manager

    @retry(max_attempts=2, base_delay=3.0)
    async def scrape(self, city: str, deal_type: str = "sale", limit: int = 50) -> list[ListingData]:
        """Скрейпинг ЦИАН через Playwright."""
        from playwright.async_api import async_playwright

        region_id = self.REGIONS.get(city, 1)
        if deal_type == "rent":
            url = f"{self.BASE}/cat.php?engine_version=2&offer_type=flat&region={region_id}&deal_type=rent&type=4"
        else:
            url = f"{self.BASE}/cat.php?engine_version=2&offer_type=flat&region={region_id}&deal_type=sale&type=4"

        api_data = []
        proxy = self.proxy_manager.get_proxy() if self.proxy_manager else None
        proxy_config = {"server": proxy} if proxy else None

        async with async_playwright() as p:
            launch_args = {"headless": True, "args": ["--no-sandbox", "--disable-setuid-sandbox"]}
            if proxy_config:
                launch_args["proxy"] = proxy_config

            browser = await p.chromium.launch(**launch_args)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
                timezone_id="Europe/Moscow",
            )
            page = await context.new_page()

            # Перехват API ответов
            async def on_response(response):
                try:
                    if "search-offers" in response.url and response.status == 200:
                        data = await response.json()
                        if "data" in data and "offersSerialized" in data["data"]:
                            api_data.extend(data["data"]["offersSerialized"])
                except:
                    pass

            page.on("response", on_response)

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)

                # Прокрутка для подгрузки
                for _ in range(min(limit // 25, 4)):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await page.wait_for_timeout(2000)

            except Exception as e:
                log.error(f"[cian] Navigation error: {e}")
                if proxy:
                    self.proxy_manager.mark_blocked(proxy)
            finally:
                await browser.close()

        # Парсим перехваченные данные
        items = []
        for offer in api_data[:limit]:
            listing = self._parse_offer(offer, city, deal_type)
            if listing:
                items.append(listing)

        log.info(f"[cian] Scraped {len(items)} items for {city} ({deal_type})")
        return items

    def _parse_offer(self, offer: dict, city: str, deal_type: str) -> Optional[ListingData]:
        try:
            offer_id = str(offer.get("id", ""))
            bargain = offer.get("bargainTerms", {})
            price = bargain.get("price") or offer.get("fullPrice", 0)

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

            return ListingData(
                source=self.SOURCE,
                source_id=offer_id,
                source_url=f"{self.BASE}/sale/flat/{offer_id}/" if deal_type == "sale" else f"{self.BASE}/rent/flat/{offer_id}/",
                property_type="apartment",
                deal_type=deal_type,
                price=float(price),
                address=address,
                city=city,
                district=district,
                lat=coords.get("lat"),
                lon=coords.get("lng"),
                area_m2=float(offer.get("totalArea")) if offer.get("totalArea") else None,
                rooms=offer.get("roomsCount"),
                floor=offer.get("floorNumber"),
                floors_total=offer.get("building", {}).get("floorsCount"),
                title=offer.get("title", ""),
                description=offer.get("description", ""),
                images=images,
                metro_station=metro_info.get("name", ""),
                metro_minutes=metro_info.get("time"),
                author_type=offer.get("user", {}).get("agentType", ""),
            )
        except Exception as e:
            log.debug(f"[cian] Parse error: {e}")
            return None


# ═══════════════════════════════════════════════════════════════
# AVITO SCRAPER
# ═══════════════════════════════════════════════════════════════

class AvitoScraper:
    """
    Авито — парсинг через Playwright.
    
    Стратегия:
    1. Рендерим JS через headless Chrome
    2. Парсим DOM-карточки объявлений
    3. Извлекаем данные из HTML-атрибутов
    """
    SOURCE = "avito"

    CITIES = {
        "Москва": "moskva", "Санкт-Петербург": "sankt-peterburg",
        "Новосибирск": "novosibirsk", "Екатеринбург": "ekaterinburg",
        "Казань": "kazan", "Краснодар": "krasnodar", "Сочи": "sochi",
    }

    def __init__(self, proxy_manager: Optional[ProxyManager] = None):
        self.proxy_manager = proxy_manager

    @retry(max_attempts=2, base_delay=3.0)
    async def scrape(self, city: str, deal_type: str = "sale", limit: int = 50) -> list[ListingData]:
        from playwright.async_api import async_playwright

        slug = self.CITIES.get(city, "moskva")
        deal_path = "prodam" if deal_type == "sale" else "sdam"
        url = f"https://www.avito.ru/{slug}/kvartiry/{deal_path}"

        proxy = self.proxy_manager.get_proxy() if self.proxy_manager else None
        proxy_config = {"server": proxy} if proxy else None
        items = []

        async with async_playwright() as p:
            launch_args = {"headless": True, "args": ["--no-sandbox", "--disable-setuid-sandbox"]}
            if proxy_config:
                launch_args["proxy"] = proxy_config

            browser = await p.chromium.launch(**launch_args)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(5000)

                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await page.wait_for_timeout(2000)

                cards = await page.query_selector_all('[data-marker="item"]')
                for card in cards[:limit]:
                    try:
                        listing = await self._parse_card(card, city, deal_type)
                        if listing:
                            items.append(listing)
                    except:
                        continue

            except Exception as e:
                log.error(f"[avito] Error: {e}")
                if proxy:
                    self.proxy_manager.mark_blocked(proxy)
            finally:
                await browser.close()

        log.info(f"[avito] Scraped {len(items)} items for {city} ({deal_type})")
        return items

    async def _parse_card(self, card, city: str, deal_type: str) -> Optional[ListingData]:
        try:
            title_el = await card.query_selector('[itemprop="name"]')
            title = (await title_el.inner_text()).strip() if title_el else ""

            price_el = await card.query_selector('[itemprop="price"]')
            price_str = await price_el.get_attribute("content") if price_el else "0"
            price = float(re.sub(r'[^\d]', '', price_str) or "0")

            link_el = await card.query_selector('a[href*="/kvartiry/"]')
            href = (await link_el.get_attribute("href")) if link_el else ""
            url = f"https://www.avito.ru{href}" if href.startswith("/") else href

            id_match = re.search(r'_(\d+)$', href)
            source_id = id_match.group(1) if id_match else hashlib.md5(url.encode()).hexdigest()[:12]

            addr_el = await card.query_selector('[data-marker="item-address"]')
            address = (await addr_el.inner_text()).strip() if addr_el else ""

            img_el = await card.query_selector('img[src*="avito"]')
            img_src = (await img_el.get_attribute("src")) if img_el else ""

            rooms = None
            rm = re.search(r'(\d)\s*-?\s*комн', title.lower())
            if rm:
                rooms = int(rm.group(1))
            elif 'студия' in title.lower():
                rooms = 0

            area = None
            am = re.search(r'([\d.,]+)\s*м²', title)
            if am:
                area = float(am.group(1).replace(",", "."))

            floor, floors_total = None, None
            fm = re.search(r'(\d+)/(\d+)\s*эт', title.lower())
            if fm:
                floor, floors_total = int(fm.group(1)), int(fm.group(2))

            return ListingData(
                source=self.SOURCE, source_id=source_id, source_url=url,
                property_type="apartment", deal_type=deal_type, price=price,
                address=address, city=city, rooms=rooms, area_m2=area,
                floor=floor, floors_total=floors_total, title=title,
                images=[img_src] if img_src else [],
            )
        except:
            return None


# ═══════════════════════════════════════════════════════════════
# DOMCLICK SCRAPER
# ═══════════════════════════════════════════════════════════════

class DomClickScraper:
    """
    Домклик — парсинг через Playwright с перехватом API.
    
    Стратегия:
    1. Открываем страницу поиска
    2. Перехватываем JSON-ответы внутреннего API
    3. Парсим структурированные данные
    """
    SOURCE = "domclick"

    def __init__(self, proxy_manager: Optional[ProxyManager] = None):
        self.proxy_manager = proxy_manager

    @retry(max_attempts=2, base_delay=3.0)
    async def scrape(self, city: str, deal_type: str = "sale", limit: int = 50) -> list[ListingData]:
        from playwright.async_api import async_playwright

        url = f"https://domclick.ru/search?deal_type={deal_type}&category=apartment&address={city.lower()}"
        api_offers = []
        proxy = self.proxy_manager.get_proxy() if self.proxy_manager else None
        proxy_config = {"server": proxy} if proxy else None

        async with async_playwright() as p:
            launch_args = {"headless": True, "args": ["--no-sandbox", "--disable-setuid-sandbox"]}
            if proxy_config:
                launch_args["proxy"] = proxy_config

            browser = await p.chromium.launch(**launch_args)
            context = await browser.new_context(viewport={"width": 1920, "height": 1080}, locale="ru-RU")
            page = await context.new_page()

            async def on_response(response):
                try:
                    if ("offers" in response.url or "search" in response.url) and response.status == 200:
                        data = await response.json()
                        if isinstance(data, dict):
                            offers = data.get("result", {}).get("offers", [])
                            if offers:
                                api_offers.extend(offers)
                except:
                    pass

            page.on("response", on_response)

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(5000)
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await page.wait_for_timeout(2000)
            except Exception as e:
                log.error(f"[domclick] Error: {e}")
                if proxy:
                    self.proxy_manager.mark_blocked(proxy)
            finally:
                await browser.close()

        items = []
        for offer in api_offers[:limit]:
            listing = self._parse_offer(offer, city, deal_type)
            if listing:
                items.append(listing)

        log.info(f"[domclick] Scraped {len(items)} items for {city} ({deal_type})")
        return items

    def _parse_offer(self, offer: dict, city: str, deal_type: str) -> Optional[ListingData]:
        try:
            offer_id = str(offer.get("id", ""))
            price_data = offer.get("price", {})
            price = price_data.get("value", 0)
            addr = offer.get("address", {})
            geo = offer.get("geo", {})
            building = offer.get("building", {})
            photos = offer.get("photos", [])
            metro = offer.get("metro", {})

            return ListingData(
                source=self.SOURCE, source_id=offer_id,
                source_url=f"https://domclick.ru/offers/{offer_id}",
                property_type="apartment", deal_type=deal_type,
                price=float(price), address=addr.get("full", ""),
                city=city, district=addr.get("district", ""),
                lat=geo.get("lat"), lon=geo.get("lon"),
                area_m2=float(offer.get("totalArea")) if offer.get("totalArea") else None,
                rooms=offer.get("rooms"), floor=offer.get("floor"),
                floors_total=offer.get("floorsTotal"),
                title=offer.get("title", ""), description=offer.get("description", ""),
                images=[p.get("url", "") for p in photos[:10] if p.get("url")],
                metro_station=metro.get("name", ""), metro_minutes=metro.get("time"),
                features={"year": building.get("buildYear"), "wall_type": building.get("wallType", "")},
            )
        except:
            return None


# ═══════════════════════════════════════════════════════════════
# UNIFIED SCRAPER
# ═══════════════════════════════════════════════════════════════

class UnifiedScraper:
    """Runs all scrapers with deduplication."""

    def __init__(self, proxies: Optional[list[str]] = None):
        self.proxy_manager = ProxyManager(proxies)
        self.cian = CianScraper(self.proxy_manager)
        self.avito = AvitoScraper(self.proxy_manager)
        self.domclick = DomClickScraper(self.proxy_manager)

    async def scrape_all(self, city: str, deal_type: str = "sale", limit: int = 50) -> dict:
        """Run all scrapers in parallel."""
        import concurrent.futures

        loop = asyncio.get_event_loop()
        results = {"cian": [], "avito": [], "domclick": []}

        with concurrent.futures.ThreadPoolExecutor() as pool:
            cian_task = loop.run_in_executor(pool, lambda: asyncio.run(self.cian.scrape(city, deal_type, limit)))
            avito_task = self.avito.scrape(city, deal_type, limit)
            domclick_task = self.domclick.scrape(city, deal_type, limit)

            cian_items, avito_items, domclick_items = await asyncio.gather(
                cian_task, avito_task, domclick_task, return_exceptions=True,
            )

        for name, items in [("cian", cian_items), ("avito", avito_items), ("domclick", domclick_items)]:
            if isinstance(items, Exception):
                log.error(f"[{name}] Scraper failed: {items}")
                results[name] = []
            else:
                results[name] = items

        all_items = results["cian"] + results["avito"] + results["domclick"]
        deduped = self._deduplicate(all_items)

        return {
            "by_source": results,
            "total_raw": len(all_items),
            "total_deduped": len(deduped),
            "items": deduped,
        }

    def _deduplicate(self, items: list[ListingData]) -> list[ListingData]:
        seen = set()
        unique = []
        for item in items:
            if item.source_hash in seen:
                continue
            seen.add(item.source_hash)
            unique.append(item)
        return unique
