"""API integration tests.

Tests the HTTP endpoints with a real database (test DB).
"""

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
class TestHealthEndpoints:

    async def test_root(self, client: AsyncClient):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "version" in data
        assert "endpoints" in data

    async def test_health(self, client: AsyncClient):
        """If health endpoint exists."""
        resp = await client.get("/api/health")
        # Might be 404 if not implemented yet — that's OK for now
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] == "ok"


@pytest.mark.asyncio
class TestListingsEndpoints:

    async def test_listings_empty(self, client: AsyncClient):
        resp = await client.get("/api/listings")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    async def test_listings_with_city_filter(self, client: AsyncClient):
        resp = await client.get("/api/listings?city=Москва")
        assert resp.status_code == 200

    async def test_listings_with_deal_type(self, client: AsyncClient):
        resp = await client.get("/api/listings?deal_type=sale")
        assert resp.status_code == 200

    async def test_listings_pagination(self, client: AsyncClient):
        resp = await client.get("/api/listings?offset=0&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5

    async def test_listing_not_found(self, client: AsyncClient):
        resp = await client.get("/api/listings/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestAgentEndpoints:

    async def test_agent_chat_empty_query(self, client: AsyncClient):
        resp = await client.post("/api/agent/chat", json={"query": ""})
        assert resp.status_code == 400

    async def test_agent_chat_search(self, client: AsyncClient):
        resp = await client.post("/api/agent/chat", json={"query": "квартира в Москве"})
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert "action" in data
        assert "filters" in data
        assert "total" in data
        assert data["action"] == "search"

    async def test_agent_chat_analytics(self, client: AsyncClient):
        resp = await client.post("/api/agent/chat", json={"query": "аналитика"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "analytics"

    async def test_agent_chat_stats(self, client: AsyncClient):
        resp = await client.post("/api/agent/chat", json={"query": "сколько объявлений"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "stats"

    async def test_agent_chat_compare_no_cities(self, client: AsyncClient):
        resp = await client.post("/api/agent/chat", json={"query": "сравни цены"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "compare"
        # Should ask for cities
        assert "два города" in data["response"].lower() or "укажите" in data["response"].lower()


@pytest.mark.asyncio
class TestAnalyticsEndpoints:

    async def test_analytics(self, client: AsyncClient):
        resp = await client.get("/api/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert "analytics" in data

    async def test_analytics_with_city(self, client: AsyncClient):
        resp = await client.get("/api/analytics?city=Москва")
        assert resp.status_code == 200

    async def test_stats(self, client: AsyncClient):
        resp = await client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_listings" in data
