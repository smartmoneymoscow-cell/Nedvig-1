"""N1.ru scraper — Russian real estate aggregator."""

import httpx
import asyncio
import json
import re
import logging
from typing import Optional
from app.scrapers.base import BaseScraper, ScrapedItem

log = logging.getLogger("realty")

CITY_SLUGS = {
    "Москва": "moskva",
    "Санкт-Петербург": "sankt-peterburg",
    "Новосибирск": "novosibirsk",
    "Екатеринбург": "ekaterinburg",
    "Казань": "kazan",
    "Краснодар": "krasnodar",
    "Сочи": "sochi",
    "Владивосток": "vladivostok",
    "Самара": "samara",
    "Уфа": "ufa",
    "Красноярск": "krasnoyarsk",
    "Пермь": "perm",
    "Воронеж": "voronezh",
}


class N1Scraper(BaseScraper):
    """
    N1.ru scraper — second largest aggregator after CIAN.
    Uses JSON API embedded in search pages.
    """
    SOURCE_NAME = "n1"
    BASE_URL = "https://www.n1.ru"

    def __init__(self, proxy: Optional[str] = None):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9",
            },
        )
        self.delay = 2.0

    async def scrape_listings(
        self,
        city: str,
        deal_type: str = "sale",
        max_pages: int = 5,
        property_type: str = "apartment",
    ) -> list[ScrapedItem]:
        """Scrape N1.ru via HTML parsing."""
        slug = CITY_SLUGS.get(city, "moskva")
        deal_path = "prodazha" if deal_type == "sale" else "arenda"
        ptype_map = {"apartment": "kvartiry", "house": "doma", "commercial": "kommercheskaya"}
        ptype_path = ptype_map.get(property_type, "kvartiry")

        items = []
        for page in range(1, max_pages + 1):
            url = f"{self.BASE_URL}/{deal_path}/{ptype_path}/{slug}/?page={page}"

            try:
                await asyncio.sleep(self.delay)
                resp = await self.client.get(url)
                resp.raise_for_status()
                html = resp.text
            except httpx.HTTPStatusError as e:
                log.warning(f"[n1] HTTP {e.response.status_code} for {city} page {page}")
                break
            except Exception as e:
                log.warning(f"[n1] Error for {city} page {page}: {e}")
                break

            # Try to extract JSON data from page
            json_items = self._extract_json_from_html(html)
            if json_items:
                for data in json_items:
                    item = self._parse_json_item(data, city, deal_type)
                    if item:
                        items.append(item)
            else:
                # Fallback: HTML parsing
                parsed = self._parse_html_page(html, city, deal_type)
                items.extend(parsed)

            log.info(f"[n1] {city}: page {page}, total {len(items)} items")

        log.info(f"[n1] {city} total: {len(items)} items")
        return items

    def _extract_json_from_html(self, html: str) -> list[dict]:
        """Try to find JSON-LD or embedded data in HTML."""
        # Look for __NEXT_DATA__ or similar JSON blocks
        patterns = [
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'"offers"\s*:\s*(\[.*?\])',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict):
                        # Navigate to offers list
                        offers = self._find_offers_in_dict(data)
                        if offers:
                            return offers
                except json.JSONDecodeError:
                    continue
        return []

    def _find_offers_in_dict(self, data: dict, depth: int = 0) -> list:
        """Recursively find offers list in nested dict."""
        if depth > 5:
            return []
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "price" in data[0]:
            return data
        for key in ["offers", "items", "results", "listings", "data"]:
            if key in data:
                if isinstance(data[key], list):
                    return data[key]
                elif isinstance(data[key], dict):
                    result = self._find_offers_in_dict(data[key], depth + 1)
                    if result:
                        return result
        return []

    def _parse_json_item(self, data: dict, city: str, deal_type: str) -> Optional[ScrapedItem]:
        """Parse a JSON offer item."""
        try:
            offer_id = str(data.get("id", data.get("externalId", "")))
            price = data.get("price", {})
            if isinstance(price, dict):
                price_val = price.get("value", price.get("total", 0))
            else:
                price_val = price

            if not price_val:
                return None

            address = data.get("address", "")
            if isinstance(address, dict):
                address = address.get("full", address.get("title", ""))

            rooms = data.get("rooms", data.get("roomsCount"))
            area = data.get("area", data.get("totalArea"))
            if isinstance(area, dict):
                area = area.get("total", area.get("value"))

            floor = data.get("floor", data.get("floorNumber"))
            floors_total = data.get("floorsTotal", data.get("building", {}).get("floorsCount"))

            return ScrapedItem(
                source=self.SOURCE_NAME,
                source_id=offer_id,
                source_url=f"{self.BASE_URL}/offer/{offer_id}",
                property_type="apartment",
                deal_type=deal_type,
                price=float(price_val),
                address=str(address),
                city=city,
                rooms=rooms,
                area_m2=float(area) if area else None,
                floor=floor,
                floors_total=floors_total,
                description=data.get("title", data.get("description", "")),
            )
        except Exception as e:
            log.debug(f"[n1] JSON parse error: {e}")
            return None

    def _parse_html_page(self, html: str, city: str, deal_type: str) -> list[ScrapedItem]:
        """Fallback HTML parsing."""
        from selectolax.parser import HTMLParser
        tree = HTMLParser(html)
        items = []

        cards = tree.css("[class*='snippet']") or tree.css("[class*='card']") or tree.css("article")
        for card in cards:
            try:
                title_el = card.css_first("a[title]") or card.css_first("h2") or card.css_first("h3")
                price_el = card.css_first("[class*='price']")
                link_el = card.css_first("a[href]")

                if not title_el:
                    continue

                title = title_el.text(strip=True)
                price_text = price_el.text(strip=True) if price_el else "0"
                price_match = re.search(r"([\d\s]+)", price_text.replace("\xa0", " "))
                price = float(price_match.group(1).replace(" ", "")) if price_match else 0

                if not price:
                    continue

                link = ""
                if link_el:
                    href = link_el.attributes.get("href", "")
                    link = f"{self.BASE_URL}{href}" if href.startswith("/") else href

                rooms = None
                rm = re.search(r"(\d)\s*-?\s*комн", title.lower())
                if rm:
                    rooms = int(rm.group(1))

                area = None
                am = re.search(r"([\d.,]+)\s*м²", title)
                if am:
                    area = float(am.group(1).replace(",", "."))

                items.append(ScrapedItem(
                    source=self.SOURCE_NAME,
                    source_id=str(hash(link or title)),
                    source_url=link,
                    property_type="apartment",
                    deal_type=deal_type,
                    price=price,
                    address="",
                    city=city,
                    rooms=rooms,
                    area_m2=area,
                    description=title,
                ))
            except Exception:
                continue

        return items

    async def close(self):
        await self.client.aclose()
