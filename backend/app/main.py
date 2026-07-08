"""Realty Platform — FastAPI main app."""

import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.routes import router
from app.api.auth_routes import router as auth_router
from app.models.database import init_db
from app.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("realty")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown."""
    await init_db()
    log.info("✅ Database initialized")

    # Auto-seed if database is empty
    from sqlalchemy import select, func
    from app.models.database import async_session
    from app.models.listing import Listing

    async with async_session() as session:
        count = (await session.execute(select(func.count(Listing.id)))).scalar()
        if count == 0:
            log.info("📦 Database empty, seeding sample data...")
            from app.data.seed import SAMPLE_LISTINGS
            from app.models.listing import PropertyType, DealType
            sources = ["cian", "avito", "domclick", "n1", "yandex", "irr", "bn"]
            for i, data in enumerate(SAMPLE_LISTINGS):
                listing = Listing(
                    source=sources[i % len(sources)],
                    source_id=f"seed_{i}",
                    source_url=f"https://example.com/listing/{i}",
                    property_type=PropertyType(data["property_type"]),
                    deal_type=DealType(data["deal_type"]),
                    price=data["price"],
                    currency="RUB",
                    area_m2=data.get("area_m2"),
                    rooms=data.get("rooms"),
                    floor=data.get("floor"),
                    floors_total=data.get("floors_total"),
                    address=data["address"],
                    district=data.get("district"),
                    city=data["city"],
                    description=data.get("description"),
                    lat=data.get("lat"),
                    lon=data.get("lon"),
                )
                session.add(listing)
            await session.commit()
            log.info(f"✅ Seeded {len(SAMPLE_LISTINGS)} listings")

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.2.0",
    lifespan=lifespan,
)

# CORS — only allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler — no internal details leaked
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )

# Routes
app.include_router(router)
app.include_router(auth_router)


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "0.3.0",
        "docs": "/docs",
        "endpoints": {
            "agent": "POST /api/agent/chat",
            "listings": "GET /api/listings",
            "analytics": "GET /api/analytics",
            "stats": "GET /api/stats",
            "auth": "POST /api/auth/register",
            "health": "GET /api/health",
        },
    }


@app.get("/api/health")
async def health():
    """Health check — verifies DB connectivity. Redis/ES are optional."""
    from sqlalchemy import text

    checks = {"status": "ok", "version": "0.3.0"}

    # DB check
    try:
        from app.models.database import async_session
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        checks["status"] = "degraded"

    # Redis check (optional)
    try:
        from app.services.cache import CacheService
        cache = CacheService()
        if await cache.ping():
            checks["redis"] = "ok"
        else:
            checks["redis"] = "unavailable"
    except Exception:
        checks["redis"] = "disabled"

    return checks
