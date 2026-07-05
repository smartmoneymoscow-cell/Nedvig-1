"""CIAN scraper — example of a real estate site scraper."""

import re
import json
from typing import Optional
from app.scrapers.base import BaseScraper, ScrapedItem

CITY_URL_MAP = {
    "Москва": "moskva",
    "Санкт-Петербург": "sankt-peterburg",
    "Новосибирск": "novosibirsk",
    "Екатеринбург": "ekaterinburg",
    "Казань": "kazan",
    "Краснодар": "krasnodar",
    "Сочи": "sochi",
}


class CianScraper(BaseScraper):
    SOURCE_NAME = "cian"
    BASE_URL = "https://www.cian.ru"

    def _build_url(self, city: str, deal_type: str, page: int = 1) -> str:
        city_slug = CITY_URL_MAP.get(city, "moskva")
        if deal_type == "rent":
            return f"{self.BASE_URL}/snyat-kvartiru/{city_slug}/?p={page}"
        return f"{self.BASE_URL}/prodazha-kvartiry/{city_slug}/?p={page}"

    async def scrape_listings(self, city: str, deal_type: str = "sale", max_pages: int = 5) -> list[ScrapedItem]:
        items = []

        for page in range(1, max_pages + 1):
            url = self._build_url(city, deal_type, page)
            html = await self.fetch_page(url)
            if not html:
                continue

            tree = self.parse_html(html)

            # CIAN uses data attributes on article cards
            cards = tree.css("article[data-name='CardComponent']") or tree.css("[data-name='SnippetV2']")
            if not cards:
                # Fallback: try generic listing containers
                cards = tree.css("[class*='listing'] [class*='item']") or tree.css("[class*='card']")

            for card in cards:
                try:
                    item = self._parse_card(card, city, deal_type)
                    if item:
                        items.append(item)
                except Exception as e:
                    print(f"[cian] Error parsing card: {e}")
                    continue

        return items

    def _parse_card(self, card, city: str, deal_type: str) -> Optional[ScrapedItem]:
        # Try to extract data from card attributes
        data = card.attributes.get("data-json")
        if data:
            try:
                d = json.loads(data)
                return self._from_json(d, city, deal_type)
            except json.JSONDecodeError:
                pass

        # Parse from HTML structure
        title_el = card.css_first("[data-name='Title']") or card.css_first("h2") or card.css_first("a[title]")
        price_el = card.css_first("[data-name='Price']") or card.css_first("[class*='price']")
        address_el = card.css_first("[data-name='Address']") or card.css_first("[class*='address']")
        link_el = card.css_first("a[href*='/cat.php']") or card.css_first("a[href*='cian.ru']") or card.css_first("a")

        if not title_el:
            return None

        # Extract price
        price = 0.0
        if price_el:
            price_text = price_el.text(strip=True)
            price_match = re.search(r"([\d\s]+)", price_text.replace("\xa0", " "))
            if price_match:
                price = float(price_match.group(1).replace(" ", ""))

        # Extract link
        link = ""
        if link_el:
            href = link_el.attributes.get("href", "")
            if href.startswith("/"):
                link = f"{self.BASE_URL}{href}"
            else:
                link = href

        # Extract rooms from title
        title = title_el.text(strip=True)
        rooms = None
        rooms_match = re.search(r"(\d)\s*-?\s*комн", title.lower())
        if rooms_match:
            rooms = int(rooms_match.group(1))
        elif "студия" in title.lower():
            rooms = 0

        # Extract area
        area = None
        area_match = re.search(r"([\d.,]+)\s*м²", title)
        if area_match:
            area = float(area_match.group(1).replace(",", "."))

        # Address
        address = address_el.text(strip=True) if address_el else ""

        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=link.split("/")[-2] if link else str(hash(title)),
            source_url=link,
            property_type="apartment",
            deal_type=deal_type,
            price=price,
            address=address,
            city=city,
            rooms=rooms,
            area_m2=area,
            description=title,
        )

    def _from_json(self, data: dict, city: str, deal_type: str) -> Optional[ScrapedItem]:
        """Parse from CIAN's JSON data attribute."""
        try:
            return ScrapedItem(
                source=self.SOURCE_NAME,
                source_id=str(data.get("id", "")),
                source_url=data.get("fullUrl", data.get("url", "")),
                property_type="apartment",
                deal_type=deal_type,
                price=float(data.get("price", data.get("bargainTerms", {}).get("price", 0))),
                address=data.get("address", data.get("geo", {}).get("userInput", "")),
                city=city,
                rooms=data.get("roomsCount"),
                area_m2=data.get("totalArea"),
                floor=data.get("floorNumber"),
                floors_total=data.get("building", {}).get("floorsCount"),
                description=data.get("title", ""),
                images=[img.get("url", "") for img in data.get("photos", [])[:5]],
                lat=data.get("geo", {}).get("coordinates", {}).get("lat"),
                lon=data.get("geo", {}).get("coordinates", {}).get("lng"),
            )
        except Exception:
            return None
