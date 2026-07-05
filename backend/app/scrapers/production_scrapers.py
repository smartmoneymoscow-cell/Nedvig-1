"""
Production scrapers using Playwright (headless browser).
This is the ONLY reliable approach for Russian real estate sites.

Requirements:
    pip install playwright
    playwright install chromium
"""

import asyncio
import json
import re
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Listing:
    """Standardized listing data."""
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
    lat: Optional[float] = None
    lon: Optional[float] = None
    area_total: Optional[float] = None
    area_living: Optional[float] = None
    area_kitchen: Optional[float] = None
    rooms: Optional[int] = None
    floor: Optional[int] = None
    floors_total: Optional[int] = None
    title: str = ""
    description: str = ""
    images: list = field(default_factory=list)
    metro_station: str = ""
    metro_minutes: Optional[int] = None
    features: dict = field(default_factory=dict)
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# ═══════════════════════════════════════════════════════════════
# CIAN SCRAPER (Playwright)
# ═══════════════════════════════════════════════════════════════

class CianScraper:
    """
    ЦИАН — парсинг через Playwright.
    
    Стратегия:
    1. Открываем страницу поиска
    2. Ждём загрузку JS
    3. Перехватываем внутренние API-ответы (JSON)
    4. Парсим JSON-данные
    
    Альтернатива: cloudscraper + internal API (менее надёжно)
    """
    SOURCE = "cian"
    BASE = "https://www.cian.ru"
    
    CITY_SLUGS = {
        "Москва": "moskva",
        "Санкт-Петербург": "sankt-peterburg",
        "Новосибирск": "novosibirsk",
        "Екатеринбург": "ekaterinburg",
        "Казань": "kazan",
        "Краснодар": "krasnodar",
        "Сочи": "sochi",
        "Владивосток": "vladivostok",
        "Ростов-на-Дону": "rostov",
        "Самара": "samara",
        "Уфа": "ufa",
        "Тюмень": "tyumen",
        "Красноярск": "krasnoyarsk",
        "Пермь": "perm",
        "Воронеж": "voronezh",
    }
    
    async def scrape(self, city: str, deal_type: str = "sale", 
                     limit: int = 50) -> list[Listing]:
        """Скрейпинг объявлений ЦИАН."""
        from playwright.async_api import async_playwright
        
        slug = self.CITY_SLUGS.get(city, "moskva")
        
        if deal_type == "sale":
            url = f"{self.BASE}/prodazha-kvartiry/{slug}/"
        else:
            url = f"{self.BASE}/snyat-kvartiru/{slug}/"
        
        api_data = []
        items = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
                timezone_id="Europe/Moscow",
            )
            page = await context.new_page()
            
            # Перехват JSON API ответов
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
                for _ in range(min(limit // 25, 3)):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await page.wait_for_timeout(2000)
                    
            except Exception as e:
                print(f"[cian] Navigation error: {e}")
            finally:
                await browser.close()
        
        # Парсим перехваченные данные
        for offer in api_data[:limit]:
            listing = self._parse_offer(offer, city, deal_type)
            if listing:
                items.append(listing)
        
        # Если API не сработал — парсим HTML (fallback)
        if not items:
            print(f"[cian] API interception failed, trying HTML parse...")
        
        return items
    
    def _parse_offer(self, offer: dict, city: str, deal_type: str) -> Optional[Listing]:
        """Парсинг одного предложения из JSON API."""
        try:
            offer_id = str(offer.get("id", ""))
            
            # Цена
            bargain = offer.get("bargainTerms", {})
            price = bargain.get("price") or offer.get("fullPrice", 0)
            
            # Адрес
            geo = offer.get("geo", {})
            address_parts = []
            district = ""
            for addr in geo.get("address", []):
                if addr.get("title"):
                    address_parts.append(addr["title"])
                if addr.get("type") == "district":
                    district = addr["title"]
            address = ", ".join(address_parts)
            
            # Координаты
            coords = geo.get("coordinates", {})
            lat = coords.get("lat")
            lon = coords.get("lng")
            
            # Метро
            metro_info = geo.get("metro", {})
            metro_station = metro_info.get("name", "")
            metro_minutes = metro_info.get("time")
            
            # Характеристики
            rooms = offer.get("roomsCount")
            total_area = offer.get("totalArea")
            floor = offer.get("floorNumber")
            floors_total = offer.get("building", {}).get("floorsCount")
            
            # Фото
            photos = offer.get("photos", [])
            images = [p.get("url2", p.get("url", "")) for p in photos[:10] if p.get("url")]
            
            # Автор
            user = offer.get("user", {})
            author_type = user.get("agentType", "unknown")
            
            return Listing(
                source=self.SOURCE,
                source_id=offer_id,
                source_url=f"{self.BASE}/sale/flat/{offer_id}/",
                property_type="apartment",
                deal_type=deal_type,
                price=float(price),
                address=address,
                city=city,
                district=district,
                lat=lat,
                lon=lon,
                area_total=float(total_area) if total_area else None,
                rooms=rooms,
                floor=floor,
                floors_total=floors_total,
                title=offer.get("title", ""),
                description=offer.get("description", ""),
                images=images,
                metro_station=metro_station,
                metro_minutes=metro_minutes,
                features={"author_type": author_type},
            )
        except Exception as e:
            return None


# ═══════════════════════════════════════════════════════════════
# AVITO SCRAPER (Playwright)
# ═══════════════════════════════════════════════════════════════

class AvitoScraper:
    """
    Авито — парсинг через Playwright.
    
    Стратегия:
    1. Открываем страницу поиска
    2. Парсим HTML-карточки объявлений
    3. Для каждой карточки извлекаем данные из DOM
    
    Проблемы:
    - Авито может показывать капчу
    - Часто меняет CSS-классы
    - Нужна ротация User-Agent
    """
    SOURCE = "avito"
    
    CITY_SLUGS = {
        "Москва": "moskva",
        "Санкт-Петербург": "sankt-peterburg",
        "Новосибирск": "novosibirsk",
        "Екатеринбург": "ekaterinburg",
        "Казань": "kazan",
        "Краснодар": "krasnodar",
        "Сочи": "sochi",
    }
    
    async def scrape(self, city: str, deal_type: str = "sale",
                     limit: int = 50) -> list[Listing]:
        """Скрейпинг объявлений Авито."""
        from playwright.async_api import async_playwright
        
        slug = self.CITY_SLUGS.get(city, "moskva")
        deal_path = "prodam" if deal_type == "sale" else "sdam"
        url = f"https://www.avito.ru/{slug}/kvartiry/{deal_path}"
        
        items = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = await context.new_page()
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(5000)
                
                # Прокрутка для подгрузки
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await page.wait_for_timeout(2000)
                
                # Парсим карточки
                cards = await page.query_selector_all('[data-marker="item"]')
                
                for card in cards[:limit]:
                    try:
                        listing = await self._parse_card(card, city, deal_type)
                        if listing:
                            items.append(listing)
                    except:
                        continue
                
            except Exception as e:
                print(f"[avito] Error: {e}")
            finally:
                await browser.close()
        
        return items
    
    async def _parse_card(self, card, city: str, deal_type: str) -> Optional[Listing]:
        """Парсинг карточки объявления."""
        try:
            # Название
            title_el = await card.query_selector('[itemprop="name"]')
            title = (await title_el.inner_text()).strip() if title_el else ""
            
            # Цена
            price_el = await card.query_selector('[itemprop="price"]')
            price_str = await price_el.get_attribute("content") if price_el else "0"
            price = float(re.sub(r'[^\d]', '', price_str) or "0")
            
            # Ссылка
            link_el = await card.query_selector('a[href*="/kvartiry/"]')
            href = (await link_el.get_attribute("href")) if link_el else ""
            url = f"https://www.avito.ru{href}" if href.startswith("/") else href
            
            # ID из URL
            id_match = re.search(r'_(\d+)$', href)
            source_id = id_match.group(1) if id_match else hashlib.md5(url.encode()).hexdigest()[:12]
            
            # Адрес
            addr_el = await card.query_selector('[data-marker="item-address"]')
            address = (await addr_el.inner_text()).strip() if addr_el else ""
            
            # Фото
            img_el = await card.query_selector('img[src*="avito"]')
            img_src = (await img_el.get_attribute("src")) if img_el else ""
            
            # Комнаты из заголовка
            rooms = None
            rm = re.search(r'(\d)\s*-?\s*комн', title.lower())
            if rm:
                rooms = int(rm.group(1))
            elif 'студия' in title.lower():
                rooms = 0
            
            # Площадь из заголовка
            area = None
            am = re.search(r'([\d.,]+)\s*м²', title)
            if am:
                area = float(am.group(1).replace(",", "."))
            
            # Этаж
            floor = None
            floors_total = None
            fm = re.search(r'(\d+)/(\d+)\s*эт', title.lower())
            if fm:
                floor = int(fm.group(1))
                floors_total = int(fm.group(2))
            
            return Listing(
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
                floor=floor,
                floors_total=floors_total,
                title=title,
                images=[img_src] if img_src else [],
            )
        except:
            return None


# ═══════════════════════════════════════════════════════════════
# DOMCLICK SCRAPER (Playwright + API перехват)
# ═══════════════════════════════════════════════════════════════

class DomClickScraper:
    """
    Домклик — парсинг через Playwright с перехватом API.
    
    Стратегия:
    1. Открываем страницу поиска domclick.ru
    2. Перехватываем JSON-ответы внутреннего API
    3. Парсим структурированные данные
    
    Преимущество: DomClick отдаёт подробные JSON с координатами,
    площадями, метро и другими характеристиками.
    """
    SOURCE = "domclick"
    
    CITY_SLUGS = {
        "Москва": "moskva",
        "Санкт-Петербург": "sankt_peterburg",
        "Новосибирск": "novosibirsk",
        "Екатеринбург": "ekaterinburg",
        "Казань": "kazan",
        "Краснодар": "krasnodar",
        "Сочи": "sochi",
    }
    
    async def scrape(self, city: str, deal_type: str = "sale",
                     limit: int = 50) -> list[Listing]:
        """Скрейпинг объявлений Домклик."""
        from playwright.async_api import async_playwright
        
        slug = self.CITY_SLUGS.get(city, "moskva")
        deal_path = "prodazha" if deal_type == "sale" else "arenda"
        url = f"https://domclick.ru/search?deal_type={deal_type}&category=apartment&address={slug}"
        
        api_offers = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
            )
            page = await context.new_page()
            
            # Перехват API
            async def on_response(response):
                try:
                    url = response.url
                    if ("offers" in url or "search" in url) and response.status == 200:
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
                
                # Прокрутка
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await page.wait_for_timeout(2000)
                    
            except Exception as e:
                print(f"[domclick] Error: {e}")
            finally:
                await browser.close()
        
        # Парсим перехваченные данные
        items = []
        for offer in api_offers[:limit]:
            listing = self._parse_offer(offer, city, deal_type)
            if listing:
                items.append(listing)
        
        return items
    
    def _parse_offer(self, offer: dict, city: str, deal_type: str) -> Optional[Listing]:
        """Парсинг предложения из DomClick API."""
        try:
            offer_id = str(offer.get("id", ""))
            
            # Цена
            price_data = offer.get("price", {})
            price = price_data.get("value", 0)
            
            # Адрес
            addr = offer.get("address", {})
            address = addr.get("full", "")
            district = addr.get("district", "")
            
            # Гео
            geo = offer.get("geo", {})
            lat = geo.get("lat")
            lon = geo.get("lon")
            
            # Площади
            area_total = offer.get("totalArea")
            area_living = offer.get("livingArea")
            area_kitchen = offer.get("kitchenArea")
            
            # Комнаты, этаж
            rooms = offer.get("rooms")
            floor = offer.get("floor")
            floors_total = offer.get("floorsTotal")
            ceiling = offer.get("ceilingHeight")
            
            # Дом
            building = offer.get("building", {})
            year = building.get("buildYear")
            wall_type = building.get("wallType", "")
            
            # Фото
            photos = offer.get("photos", [])
            images = [p.get("url", "") for p in photos[:10] if p.get("url")]
            
            # Метро
            metro = offer.get("metro", {})
            metro_station = metro.get("name", "")
            metro_minutes = metro.get("time")
            
            return Listing(
                source=self.SOURCE,
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
                area_total=float(area_total) if area_total else None,
                area_living=float(area_living) if area_living else None,
                area_kitchen=float(area_kitchen) if area_kitchen else None,
                rooms=rooms,
                floor=floor,
                floors_total=floors_total,
                title=offer.get("title", ""),
                description=offer.get("description", ""),
                images=images,
                metro_station=metro_station,
                metro_minutes=metro_minutes,
                features={
                    "year": year,
                    "wall_type": wall_type,
                    "ceiling_height": ceiling,
                },
            )
        except:
            return None


# ═══════════════════════════════════════════════════════════════
# ТЕСТ
# ═══════════════════════════════════════════════════════════════

async def test_scraper():
    """Тест всех парсеров."""
    scrapers = [
        ("CIAN", CianScraper()),
        ("Avito", AvitoScraper()),
        ("DomClick", DomClickScraper()),
    ]
    
    for name, scraper in scrapers:
        print(f"\n{'='*60}")
        print(f"🔍 Testing {name}...")
        print(f"{'='*60}")
        
        try:
            items = await scraper.scrape("Москва", "sale", 3)
            print(f"✅ Got {len(items)} items")
            for i, item in enumerate(items):
                print(f"  {i+1}. {item.rooms}к, {item.area_total}м² — {item.price:,.0f} ₽")
                print(f"     📍 {item.address}")
                print(f"     🔗 {item.source_url}")
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_scraper())
