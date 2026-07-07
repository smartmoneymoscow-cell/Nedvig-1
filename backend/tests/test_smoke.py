"""Smoke tests — verify app starts and basic endpoints respond."""

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    """Health check returns 200 with status."""
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert "database" in body


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    """Root returns app info."""
    r = await client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert "endpoints" in data


@pytest.mark.asyncio
async def test_listings_empty(client: AsyncClient):
    """Listings endpoint works with empty DB."""
    r = await client.get("/api/listings")
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "items" in data


@pytest.mark.asyncio
async def test_analytics_empty(client: AsyncClient):
    """Analytics endpoint works with empty DB."""
    r = await client.get("/api/analytics")
    assert r.status_code == 200
    data = r.json()
    assert "analytics" in data


@pytest.mark.asyncio
async def test_stats_empty(client: AsyncClient):
    """Stats endpoint works with empty DB."""
    r = await client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert "total_listings" in data


@pytest.mark.asyncio
async def test_agent_chat_requires_query(client: AsyncClient):
    """Agent chat requires query field."""
    r = await client.post("/api/agent/chat", json={})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_agent_chat_empty_query(client: AsyncClient):
    """Agent chat rejects empty query."""
    r = await client.post("/api/agent/chat", json={"query": ""})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_agent_chat_valid(client: AsyncClient):
    """Agent chat accepts valid query."""
    r = await client.post("/api/agent/chat", json={"query": "квартира в Москве"})
    assert r.status_code == 200
    data = r.json()
    assert "response" in data
    assert "action" in data


@pytest.mark.asyncio
async def test_listings_with_filters(client: AsyncClient):
    """Listings endpoint accepts filters."""
    r = await client.get("/api/listings?city=Москва&deal_type=sale&rooms=2")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_analytics_compare(client: AsyncClient):
    """Analytics compare endpoint works."""
    r = await client.get("/api/analytics/compare?city1=Москва&city2=Санкт-Петербург")
    assert r.status_code == 200
    data = r.json()
    assert "comparison" in data


@pytest.mark.asyncio
async def test_docs_available(client: AsyncClient):
    """Swagger docs available."""
    r = await client.get("/docs")
    assert r.status_code == 200
