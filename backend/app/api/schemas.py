"""Pydantic schemas for API request/response validation."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)


class ChatResponse(BaseModel):
    response: str
    action: str
    filters: dict
    total: int


class ListingResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[dict]


class HealthResponse(BaseModel):
    status: str
    version: str
    listings_count: int


class StatsResponse(BaseModel):
    total_listings: int
    by_source: dict
    top_cities: dict
