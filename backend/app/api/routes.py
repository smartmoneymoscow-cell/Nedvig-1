"""API routes — search, analytics, agent, scraping."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.database import get_db
from app.models.listing import Listing, PropertyType, DealType
from app.services.search import SearchService, SearchFilters
from app.ai.agent import AIAgent

router = APIRouter()
agent = AIAgent()


# ─── AI Agent Chat ───────────────────────────────────────────────

@router.post("/api/agent/chat")
async def agent_chat(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Natural language query → structured search + response."""
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(400, "Query is required")

    filters, action = agent.parse_query(query)
    search = SearchService(db)

    try:
        if action == "analytics":
            data = await search.get_analytics(city=filters.city)
        elif action == "compare":
            # For compare, need two cities — extract from query
            cities = []
            for alias, name in [
                ("москва", "Москва"), ("мск", "Москва"),
                ("питер", "Санкт-Петербург"), ("спб", "Санкт-Петербург"),
                ("новосибирск", "Новосибирск"), ("екатеринбург", "Екатеринбург"),
            ]:
                if alias in query.lower():
                    cities.append(name)
            if len(cities) >= 2:
                data = await search.compare_cities(cities[0], cities[1], filters.property_type)
            else:
                data = await search.search(filters)
                action = "search"
        else:
            data = await search.search(filters)

        response = agent.format_response(action, data, filters)
        return {
            "response": response,
            "action": action,
            "filters": {
                k: v for k, v in {
                    "city": filters.city,
                    "deal_type": filters.deal_type.value if filters.deal_type else None,
                    "property_type": filters.property_type.value if filters.property_type else None,
                    "price_min": filters.price_min,
                    "price_max": filters.price_max,
                    "rooms": filters.rooms_min,
                }.items() if v is not None
            },
            "total": data.get("total", 0),
        }
    finally:
        await search.close()


# ─── Listings CRUD ───────────────────────────────────────────────

@router.get("/api/listings")
async def get_listings(
    city: Optional[str] = None,
    deal_type: Optional[str] = None,
    property_type: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    rooms: Optional[int] = None,
    sort_by: str = Query("created_at", regex="^(created_at|price|area_m2)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Structured search with filters."""
    filters = SearchFilters(
        city=city,
        deal_type=DealType(deal_type) if deal_type else None,
        property_type=PropertyType(property_type) if property_type else None,
        price_min=price_min,
        price_max=price_max,
        rooms_min=rooms,
        rooms_max=rooms,
    )
    search = SearchService(db)
    try:
        return await search.search(filters, offset, limit, sort_by, sort_order)
    finally:
        await search.close()


@router.get("/api/listings/{listing_id}")
async def get_listing(listing_id: str, db: AsyncSession = Depends(get_db)):
    """Get single listing by ID."""
    from uuid import UUID
    result = await db.execute(
        select(Listing).where(Listing.id == UUID(listing_id), Listing.is_active == True)
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(404, "Listing not found")
    return listing.to_dict()


# ─── Analytics ───────────────────────────────────────────────────

@router.get("/api/analytics")
async def get_analytics(
    city: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Price analytics."""
    search = SearchService(db)
    try:
        return await search.get_analytics(city)
    finally:
        await search.close()


@router.get("/api/analytics/compare")
async def compare_cities(
    city1: str = Query(...),
    city2: str = Query(...),
    property_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Compare two cities."""
    search = SearchService(db)
    try:
        return await search.compare_cities(city1, city2, property_type)
    finally:
        await search.close()


# ─── Stats ───────────────────────────────────────────────────────

@router.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """General platform statistics."""
    total = (await db.execute(select(func.count(Listing.id)).where(Listing.is_active == True))).scalar()
    by_source = (await db.execute(
        select(Listing.source, func.count(Listing.id))
        .where(Listing.is_active == True)
        .group_by(Listing.source)
    )).all()
    by_city = (await db.execute(
        select(Listing.city, func.count(Listing.id))
        .where(Listing.is_active == True)
        .group_by(Listing.city)
        .order_by(func.count(Listing.id).desc())
        .limit(10)
    )).all()

    return {
        "total_listings": total,
        "by_source": {row[0]: row[1] for row in by_source},
        "top_cities": {row[0]: row[1] for row in by_city},
    }
