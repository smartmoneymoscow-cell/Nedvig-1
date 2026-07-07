"""Ingestion pipeline — normalizes, deduplicates, and stores scraped data."""

import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.listing import Listing, PropertyType, DealType
from app.models.database import async_session
from app.scrapers.base import ScrapedItem

log = logging.getLogger("realty")


class Normalizer:
    """Normalizes scraped data before storage."""

    @staticmethod
    def normalize_price(price: float, currency: str = "RUB") -> float:
        """Ensure price is in RUB and positive."""
        if currency == "USD":
            return price * 90  # approximate
        elif currency == "EUR":
            return price * 100
        return abs(price)

    @staticmethod
    def normalize_address(address: str) -> str:
        """Clean up address string."""
        if not address:
            return ""
        # Remove extra whitespace
        address = " ".join(address.split())
        # Remove leading/trailing commas
        address = address.strip(", ")
        return address

    @staticmethod
    def normalize_city(city: str) -> str:
        """Normalize city name."""
        city_map = {
            "москва": "Москва", "moscow": "Москва",
            "санкт-петербург": "Санкт-Петербург", "спб": "Санкт-Петербург",
            "питер": "Санкт-Петербург", "peterburg": "Санкт-Петербург",
            "новосибирск": "Новосибирск",
            "екатеринбург": "Екатеринбург",
            "казань": "Казань",
            "краснодар": "Краснодар",
            "сочи": "Сочи",
        }
        return city_map.get(city.lower().strip(), city)

    @staticmethod
    def validate(item: ScrapedItem) -> bool:
        """Check if item has minimum required data."""
        if not item.price or item.price <= 0:
            return False
        if not item.city:
            return False
        if not item.address and not item.description:
            return False
        return True


class Deduplicator:
    """Handles deduplication of listings."""

    @staticmethod
    def make_source_hash(source: str, source_id: str, price: float, address: str) -> str:
        """Hash for source-level dedup."""
        content = f"{source}:{source_id}:{price}:{address}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @staticmethod
    def make_content_hash(city: str, address: str, area: Optional[float], rooms: Optional[int], price: float) -> str:
        """Hash for cross-source dedup."""
        content = f"{city}:{address}:{area}:{rooms}:{price}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @classmethod
    async def is_duplicate(cls, session: AsyncSession, source_hash: str) -> bool:
        """Check if listing already exists by source hash."""
        result = await session.execute(
            select(Listing.id).where(Listing.source_hash == source_hash).limit(1)
        )
        return result.scalar_one_or_none() is not None

    @classmethod
    async def find_existing(cls, session: AsyncSession, source_hash: str) -> Optional[Listing]:
        """Find existing listing by source hash."""
        result = await session.execute(
            select(Listing).where(Listing.source_hash == source_hash).limit(1)
        )
        return result.scalar_one_or_none()


class IngestionPipeline:
    """Processes scraped items into database records."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.normalizer = Normalizer()
        self.stats = {
            "total": 0,
            "new": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }

    async def ingest_items(self, items: list[ScrapedItem]) -> dict:
        """Process a batch of scraped items."""
        self.stats = {"total": len(items), "new": 0, "updated": 0, "skipped": 0, "errors": 0}

        for item in items:
            try:
                await self._process_item(item)
            except Exception as e:
                log.error(f"Ingestion error for {item.source}:{item.source_id}: {e}")
                self.stats["errors"] += 1

        await self.db.commit()
        log.info(f"Ingestion complete: {self.stats}")
        return self.stats

    async def _process_item(self, item: ScrapedItem):
        """Process a single scraped item."""
        # Validate
        if not self.normalizer.validate(item):
            self.stats["skipped"] += 1
            return

        # Normalize
        price = self.normalizer.normalize_price(item.price, item.currency)
        address = self.normalizer.normalize_address(item.address)
        city = self.normalizer.normalize_city(item.city)

        # Generate hashes
        source_hash = Deduplicator.make_source_hash(item.source, item.source_id, price, address)

        # Check for existing
        existing = await Deduplicator.find_existing(self.db, source_hash)
        if existing:
            # Update if price changed
            if abs(float(existing.price) - price) > 1000:
                existing.price = price
                existing.updated_at = datetime.now(timezone.utc)
                self.stats["updated"] += 1
            else:
                self.stats["skipped"] += 1
            return

        # Create new listing
        listing = Listing(
            source=item.source,
            source_id=item.source_id,
            source_url=item.source_url or "",
            source_hash=source_hash,
            property_type=item.property_type or "apartment",
            deal_type=item.deal_type or "sale",
            price=price,
            price_per_m2=price / item.area_m2 if item.area_m2 and item.area_m2 > 0 else None,
            currency=item.currency or "RUB",
            area_m2=item.area_m2,
            rooms=item.rooms,
            floor=item.floor,
            floors_total=item.floors_total,
            address=address,
            district=item.district,
            city=city,
            region=item.region,
            lat=item.lat,
            lon=item.lon,
            title=getattr(item, "title", None) or (item.description[:200] if item.description else None),
            description=item.description,
            images=str(item.images) if item.images else "[]",
            features=str(item.features) if item.features else "{}",
        )
        self.db.add(listing)
        self.stats["new"] += 1

    async def ingest_from_scraper_result(self, scraper_result: dict) -> dict:
        """Ingest from ScraperRunner result dict."""
        items = scraper_result.get("items", [])
        return await self.ingest_items(items)
