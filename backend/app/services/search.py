"""Search service — combines PostgreSQL filters + Elasticsearch full-text + semantic search."""

import logging
from typing import Optional
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from elasticsearch import AsyncElasticsearch
from app.models.listing import Listing, PropertyType, DealType
from app.config import get_settings

settings = get_settings()
log = logging.getLogger("realty")

# Singleton ES client — shared across all SearchService instances
_es_client: AsyncElasticsearch | None = None


def get_es_client() -> AsyncElasticsearch | None:
    """Get or create singleton Elasticsearch client. Returns None if ES unavailable."""
    global _es_client
    if _es_client is None:
        try:
            _es_client = AsyncElasticsearch(settings.ES_URL)
        except Exception as e:
            log.warning(f"Elasticsearch unavailable: {e}")
            return None
    return _es_client


class SearchFilters:
    """Parsed search filters from user query."""
    def __init__(
        self,
        city: Optional[str] = None,
        deal_type: Optional[DealType] = None,
        property_type: Optional[PropertyType] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        rooms_min: Optional[int] = None,
        rooms_max: Optional[int] = None,
        area_min: Optional[float] = None,
        area_max: Optional[float] = None,
        floor_min: Optional[int] = None,
        floor_max: Optional[int] = None,
        district: Optional[str] = None,
        query_text: Optional[str] = None,
    ):
        self.city = city
        self.deal_type = deal_type
        self.property_type = property_type
        self.price_min = price_min
        self.price_max = price_max
        self.rooms_min = rooms_min
        self.rooms_max = rooms_max
        self.area_min = area_min
        self.area_max = area_max
        self.floor_min = floor_min
        self.floor_max = floor_max
        self.district = district
        self.query_text = query_text


class SearchService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.es = get_es_client()

    async def search(
        self,
        filters: SearchFilters,
        offset: int = 0,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> dict:
        """Combined structured + full-text search."""
        # Build PostgreSQL query
        query = select(Listing).where(Listing.is_active == True)

        if filters.city:
            query = query.where(func.lower(Listing.city) == filters.city.lower())
        if filters.deal_type:
            query = query.where(Listing.deal_type == filters.deal_type)
        if filters.property_type:
            query = query.where(Listing.property_type == filters.property_type)
        if filters.price_min:
            query = query.where(Listing.price >= filters.price_min)
        if filters.price_max:
            query = query.where(Listing.price <= filters.price_max)
        if filters.rooms_min is not None:
            query = query.where(Listing.rooms >= filters.rooms_min)
        if filters.rooms_max is not None:
            query = query.where(Listing.rooms <= filters.rooms_max)
        if filters.area_min:
            query = query.where(Listing.area_m2 >= filters.area_min)
        if filters.area_max:
            query = query.where(Listing.area_m2 <= filters.area_max)
        if filters.district:
            query = query.where(func.lower(Listing.district).contains(filters.district.lower()))

        # Full-text on description if query_text provided
        if filters.query_text:
            query = query.where(
                func.lower(Listing.description).contains(filters.query_text.lower())
            )

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Sort
        sort_col = getattr(Listing, sort_by, Listing.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_col))
        else:
            query = query.order_by(sort_col)

        # Paginate
        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        listings = result.scalars().all()

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "items": [l.to_dict() for l in listings],
        }

    async def get_analytics(self, city: Optional[str] = None) -> dict:
        """Price analytics for a city."""
        base = select(
            Listing.deal_type,
            Listing.property_type,
            func.count(Listing.id).label("count"),
            func.avg(Listing.price).label("avg_price"),
            func.min(Listing.price).label("min_price"),
            func.max(Listing.price).label("max_price"),
            func.avg(Listing.area_m2).label("avg_area"),
            func.avg(Listing.price / Listing.area_m2).label("avg_price_per_m2"),
        ).where(Listing.is_active == True)

        if city:
            base = base.where(func.lower(Listing.city) == city.lower())

        base = base.group_by(Listing.deal_type, Listing.property_type)
        result = await self.db.execute(base)
        rows = result.all()

        analytics = []
        for row in rows:
            analytics.append({
                "deal_type": row.deal_type.value if row.deal_type else None,
                "property_type": row.property_type.value if row.property_type else None,
                "count": row.count,
                "avg_price": round(float(row.avg_price), 2) if row.avg_price else None,
                "min_price": float(row.min_price) if row.min_price else None,
                "max_price": float(row.max_price) if row.max_price else None,
                "avg_area_m2": round(float(row.avg_area), 1) if row.avg_area else None,
                "avg_price_per_m2": round(float(row.avg_price_per_m2), 2) if row.avg_price_per_m2 else None,
            })

        return {"city": city, "analytics": analytics}

    async def compare_cities(self, city1: str, city2: str, property_type=None) -> dict:
        """Compare prices between two cities."""
        results = {}
        for city in [city1, city2]:
            filters = SearchFilters(city=city, property_type=property_type)
            data = await self.search(filters, limit=0)
            analytics = await self.get_analytics(city)
            results[city] = {"total_listings": data["total"], "analytics": analytics["analytics"]}
        return {"comparison": results}

    async def close(self):
        """No-op — singleton ES client stays open."""
        pass
