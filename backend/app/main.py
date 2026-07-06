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
        "version": "0.2.0",
        "docs": "/docs",
        "endpoints": {
            "agent": "POST /api/agent/chat",
            "listings": "GET /api/listings",
            "analytics": "GET /api/analytics",
            "stats": "GET /api/stats",
        },
    }
