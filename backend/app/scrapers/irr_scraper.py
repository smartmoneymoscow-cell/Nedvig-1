"""IRR.ru scraper — parses real estate listings."""

import httpx
import asyncio
import re
import logging
from typing import Optional
from app.scrapers.base import BaseScraper, ScrapedItem

log = logging.getLogger("realty")

CITY_SLUGS = {
    "Москва": "moskva", "Санкт-Петербург": "sankt-peterburg",
    "Новосибирск": "novosibirsk", "Екатеринбург": "ekaterinburg",
    "Казань": "kazan", "Краснодар": "krasnodar", "Сочи": "sochi",
    "Владивосток": "vladivostok", "Самара": "samara", "Уфа": "ufa",
}


class IrrScraper(BaseScraper):
    """IRR.ru — real estate section."""
    SOURCE_NAME = "irr"
    BASE_URL = "https://www.irr.ru"

    async def scrape_listings(self, city: str, deal_type: str = "sale", max_pages: int = 3) -> list[ScrapedItem]:
        items = []
        try:
            city_slug = CITY_SLUGS.get(city, "moskva")
            section = "prodam" if deal_type == "sale" else "sdam"

            for page in range(1, max_pages + 1):
                url = f"{self.BASE_URL}/real-estate/{section}/{city_slug}/page{page}/"
                html = await self.fetch_page(url)
                if not html:
                    break

                tree = self.parse_html(html)
                cards = tree.css("div.listing__item")
                if not cards:
                    break

                for card in cards:
                    try:
                        title_el = card.css_first("a.listing__itemTitle span")
                        price_el = card.css_first("div.listing__itemPrice")
                        addr_el = card.css_first("div.listing__itemAddress")
                        link_el = card.css_first("a.listing__itemTitle")

                        if not title_el or not price_el:
                            continue

                        title = title_el.text(strip=True)
                        price_text = price_el.text(strip=True)
                        price = self._parse_price(price_text)
                        if not price:
                            continue

                        address = addr_el.text(strip=True) if addr_el else ""
                        href = link_el.attributes.get("href", "")

                        items.append(ScrapedItem(
                            source=self.SOURCE_NAME,
                            source_id=href.split("/")[-1] if href else str(len(items)),
                            source_url=f"{self.BASE_URL}{href}" if href.startswith("/") else href,
                            property_type="apartment",
                            deal_type=deal_type,
                            price=price,
                            address=address,
                            city=city,
                        ))
                    except Exception as e:
                        log.debug(f"[irr] Parse error: {e}")
        except Exception as e:
            log.warning(f"[irr] Error scraping {city}: {e}")
        return items

    @staticmethod
    def _parse_price(text: str) -> Optional[float]:
        text = text.replace(" ", "").replace("₽", "").replace("руб.", "")
        try:
            return float(text)
        except ValueError:
            return None
