import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness(client: AsyncClient):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


@pytest.mark.asyncio
async def test_readiness(client: AsyncClient):
    response = await client.get("/health/ready")
    # May be 503 if postgres/redis not available in test env
    assert response.status_code in [200, 503]
    data = response.json()
    assert "healthy" in data
    assert "checks" in data
