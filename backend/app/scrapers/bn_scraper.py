"""BN.ru scraper — St. Petersburg and Northwest real estate."""

import httpx
import asyncio
import logging
from typing import Optional
from app.scrapers.base import BaseScraper, ScrapedItem

log = logging.getLogger("realty")


class BnScraper(BaseScraper):
    """BN.ru — Northwestern Russia real estate portal."""
    SOURCE_NAME = "bn"
    BASE_URL = "https://www.bn.ru"

    async def scrape_listings(self, city: str, deal_type: str = "sale", max_pages: int = 3) -> list[ScrapedItem]:
        items = []
        try:
            section = "prodazha" if deal_type == "sale" else "arenda"

            for page in range(1, max_pages + 1):
                url = f"{self.BASE_URL}/{section}/kvartiry/?page={page}"
                html = await self.fetch_page(url)
                if not html:
                    break

                tree = self.parse_html(html)
                cards = tree.css("div.catalog__item")
                if not cards:
                    break

                for card in cards:
                    try:
                        title_el = card.css_first("a.catalog__item-title")
                        price_el = card.css_first("div.catalog__item-price")
                        addr_el = card.css_first("div.catalog__item-address")

                        if not title_el or not price_el:
                            continue

                        title = title_el.text(strip=True)
                        price_text = price_el.text(strip=True)
                        price = self._parse_price(price_text)
                        if not price:
                            continue

                        address = addr_el.text(strip=True) if addr_el else ""
                        href = title_el.attributes.get("href", "")

                        items.append(ScrapedItem(
                            source=self.SOURCE_NAME,
                            source_id=href.split("/")[-2] if href else str(len(items)),
                            source_url=f"{self.BASE_URL}{href}" if href.startswith("/") else href,
                            property_type="apartment",
                            deal_type=deal_type,
                            price=price,
                            address=address or city,
                            city=city,
                        ))
                    except Exception as e:
                        log.debug(f"[bn] Parse error: {e}")
        except Exception as e:
            log.warning(f"[bn] Error scraping {city}: {e}")
        return items

    @staticmethod
    def _parse_price(text: str) -> Optional[float]:
        text = text.replace(" ", "").replace("₽", "").replace("руб.", "")
        try:
            return float(text)
        except ValueError:
            return None
