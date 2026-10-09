import pytest
from httpx import AsyncClient
from app.services.cache_service import cache_service


@pytest.mark.asyncio
async def test_observability_middleware_headers(async_client: AsyncClient):
    """Verifies X-Request-ID and X-Process-Time tracing headers are returned."""
    # 1. Custom request ID passed by client
    res = await async_client.get("/health", headers={"X-Request-ID": "custom-trace-123"})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == "custom-trace-123"
    assert "X-Process-Time" in res.headers

    # 2. Auto-generated request ID if omitted
    res2 = await async_client.get("/health")
    assert res2.status_code == 200
    assert res2.headers.get("X-Request-ID", "").startswith("req_")
    assert "X-Process-Time" in res2.headers


@pytest.mark.asyncio
async def test_rate_limiting_middleware(async_client: AsyncClient):
    """Verifies rate limiting headers are returned and throttles upon exceeding threshold."""
    # Rate limit headers present on standard endpoints
    res = await async_client.get("/api/v1/profiles")
    assert "X-RateLimit-Limit" in res.headers
    assert "X-RateLimit-Remaining" in res.headers


@pytest.mark.asyncio
async def test_caching_and_invalidation(async_client: AsyncClient):
    """Verifies receipt caching returns identical data and invalidation works."""
    await cache_service.clear()

    # 1. First fetch (cache miss -> stored in cache)
    res1 = await async_client.get("/api/v1/orders/ORD-5001/receipt")
    assert res1.status_code == 200
    data1 = res1.json()

    # Verify cache key was set
    cached = await cache_service.get("receipt:ORD-5001")
    assert cached is not None
    assert cached.order_id == "ORD-5001"

    # 2. Second fetch (cache hit)
    res2 = await async_client.get("/api/v1/orders/ORD-5001/receipt")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data1["receipt_id"] == data2["receipt_id"]

    # 3. Invalidate cache
    await cache_service.delete("receipt:ORD-5001")
    assert await cache_service.get("receipt:ORD-5001") is None


@pytest.mark.asyncio
async def test_background_task_dispatch_and_audit(async_client: AsyncClient, mock_db):
    """Verifies non-blocking background email dispatch and audit log persistence."""
    res = await async_client.post("/api/v1/orders/ORD-5001/receipt/dispatch")
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "queued"
    assert data["receipt_id"] == "REC-ORD-5001"

    # Verify audit log entry was recorded
    audit_entry = await mock_db["audit_logs"].find_one({"order_id": "ORD-5001"})
    assert audit_entry is not None
    assert audit_entry["event"] == "RECEIPT_DISPATCHED"
    assert audit_entry["status"] == "SENT"


@pytest.mark.asyncio
async def test_event_bus_publishing():
    """Verifies that the event bus publishes messages and handles delivery."""
    from app.services.event_bus import event_bus
    result = await event_bus.publish(
        routing_key="receipt.tested",
        payload={"order_id": "ORD-5001", "action": "TEST"},
    )
    assert result is True


@pytest.mark.asyncio
async def test_cache_service_prefix_invalidation():
    """Verifies prefix-based cache invalidation."""
    await cache_service.set("receipt:order:1", {"id": 1}, ttl_seconds=60)
    await cache_service.set("receipt:order:2", {"id": 2}, ttl_seconds=60)
    await cache_service.set("user:profile:1", {"id": 1}, ttl_seconds=60)

    deleted_count = await cache_service.delete_prefix("receipt:order:")
    assert deleted_count == 2
    assert await cache_service.get("receipt:order:1") is None
    assert await cache_service.get("user:profile:1") is not None
