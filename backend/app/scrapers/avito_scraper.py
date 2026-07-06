"""Avito scraper — uses HTML parsing (needs proxy for production)."""

import httpx
import asyncio
import re
import hashlib
import logging
from typing import Optional
from app.scrapers.base import ScrapedItem

log = logging.getLogger("realty")

CITY_SLUGS = {
    "Москва": "moskva", "Санкт-Петербург": "sankt-peterburg",
    "Новосибирск": "novosibirsk", "Екатеринбург": "ekaterinburg",
    "Казань": "kazan", "Краснодар": "krasnodar", "Сочи": "sochi",
    "Владивосток": "vladivostok", "Самара": "samara", "Уфа": "ufa",
}


class AvitoScraper:
    """
    Avito scraper — parses search result pages.
    NOTE: Avito blocks datacenter IPs. Needs residential proxy for production.
    """
    SOURCE_NAME = "avito"
    BASE_URL = "https://www.avito.ru"

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.delay = 3.0

    async def scrape_listings(
        self,
        city: str,
        deal_type: str = "sale",
        max_pages: int = 3,
        property_type: str = "apartment",
    ) -> list[ScrapedItem]:
        """Scrape Avito via HTML parsing."""
        slug = CITY_SLUGS.get(city, "moskva")
        deal_path = "prodam" if deal_type == "sale" else "sdam"
        ptype_path = "kvartiry" if property_type == "apartment" else property_type

        items = []
        proxy_url = f"http://{self.proxy}" if self.proxy else None

        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            proxy=proxy_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9",
                "Cache-Control": "no-cache",
            },
        ) as client:
            for page in range(1, max_pages + 1):
                url = f"{self.BASE_URL}/{slug}/{ptype_path}/{deal_path}?p={page}"

                try:
                    await asyncio.sleep(self.delay)
                    resp = await client.get(url)
                    resp.raise_for_status()
                    html = resp.text
                except httpx.HTTPStatusError as e:
                    log.warning(f"[avito] HTTP {e.response.status_code} for {city} page {page}")
                    if e.response.status_code == 403:
                        log.warning("[avito] Blocked! Need proxy.")
                        break
                    continue
                except Exception as e:
                    log.warning(f"[avito] Error: {e}")
                    break

                parsed = self._parse_page(html, city, deal_type)
                items.extend(parsed)
                log.info(f"[avito] {city}: page {page}, got {len(parsed)} items")

        log.info(f"[avito] {city} total: {len(items)} items")
        return items

    def _parse_page(self, html: str, city: str, deal_type: str) -> list[ScrapedItem]:
        """Parse Avito search results page."""
        from selectolax.parser import HTMLParser
        tree = HTMLParser(html)
        items = []

        # Avito uses data-marker="item" on listing cards
        cards = tree.css('[data-marker="item"]')
        if not cards:
            cards = tree.css('[class*="snippet"]') or tree.css('[class*="iva-item"]')

        for card in cards:
            try:
                item = self._parse_card(card, city, deal_type)
                if item:
                    items.append(item)
            except Exception:
                continue

        return items

    def _parse_card(self, card, city: str, deal_type: str) -> Optional[ScrapedItem]:
        """Parse single Avito listing card."""
        # Title
        title_el = (
            card.css_first('[itemprop="name"]') or
            card.css_first('[data-marker="item-title"]') or
            card.css_first('a[title]') or
            card.css_first('h3')
        )
        title = title_el.text(strip=True) if title_el else ""

        # Price
        price_el = card.css_first('[itemprop="price"]') or card.css_first('[data-marker="item-price"]')
        price = 0.0
        if price_el:
            price_text = price_el.attributes.get("content", "") or price_el.text(strip=True)
            price_match = re.search(r"([\d\s]+)", price_text.replace("\xa0", " "))
            if price_match:
                price = float(price_match.group(1).replace(" ", ""))

        if not price:
            return None

        # Link
        link_el = card.css_first('a[href*="/kvartiry/"]') or card.css_first('a[href]') or title_el
        href = ""
        if link_el:
            href = link_el.attributes.get("href", "")
        url = f"https://www.avito.ru{href}" if href.startswith("/") else href

        # Source ID from URL
        id_match = re.search(r'_(\d+)$', href)
        source_id = id_match.group(1) if id_match else hashlib.md5(url.encode()).hexdigest()[:12]

        # Address
        addr_el = card.css_first('[data-marker="item-address"]') or card.css_first('[class*="address"]')
        address = addr_el.text(strip=True) if addr_el else ""

        # Image
        img_el = card.css_first('img[src*="avito"]') or card.css_first('img')
        img_src = img_el.attributes.get("src", "") if img_el else ""

        # Rooms from title
        rooms = None
        rm = re.search(r'(\d)\s*-?\s*комн', title.lower())
        if rm:
            rooms = int(rm.group(1))
        elif 'студия' in title.lower():
            rooms = 0

        # Area from title
        area = None
        am = re.search(r'([\d.,]+)\s*м²', title)
        if am:
            area = float(am.group(1).replace(",", "."))

        # Floor from title
        floor, floors_total = None, None
        fm = re.search(r'(\d+)/(\d+)\s*эт', title.lower())
        if fm:
            floor, floors_total = int(fm.group(1)), int(fm.group(2))

        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=source_id,
            source_url=url,
            property_type="apartment",
            deal_type=deal_type,
            price=price,
            address=address,
            city=city,
            rooms=rooms,
            area_m2=area,
            floor=floor,
            floors_total=floors_total,
            description=title,
            images=[img_src] if img_src else [],
        )

    async def close(self):
        pass
