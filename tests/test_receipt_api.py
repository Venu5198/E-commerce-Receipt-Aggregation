import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_get_receipt_success_complete_aggregation(async_client: AsyncClient):
    response = await async_client.get("/api/v1/orders/ORD-5001/receipt")
    assert response.status_code == 200
    data = response.json()

    # Order Metadata
    assert data["order_id"] == "ORD-5001"
    assert data["receipt_id"] == "REC-ORD-5001"
    assert data["order_status"] == "DELIVERED"

    # Profile Join
    customer = data["customer"]
    assert customer["user_id"] == "USER-1001"
    assert customer["name"] == "Alice Johnson"
    assert customer["email"] == "alice.johnson@example.com"
    assert customer["is_profile_found"] is True
    assert customer["shipping_address"]["city"] == "Springfield"

    # Product Batch Join
    items = data["items"]
    assert len(items) == 2
    item1 = next(item for item in items if item["product_id"] == "PROD-001")
    assert item1["title"] == "SonicQuiet Pro ANC Headphones"
    assert item1["unit_price"] == 249.99
    assert item1["quantity"] == 1
    assert item1["total_price"] == 249.99
    assert item1["product_found"] is True

    item2 = next(item for item in items if item["product_id"] == "PROD-004")
    assert item2["title"] == "HyperPort 7-in-1 USB-C Hub"
    assert item2["unit_price"] == 45.00
    assert item2["quantity"] == 2
    assert item2["total_price"] == 90.00
    assert item2["product_found"] is True

    # Summary
    summary = data["summary"]
    assert summary["subtotal"] == 339.99
    assert summary["tax"] == 27.20
    assert summary["total_amount"] == 367.19
    assert summary["currency"] == "USD"

    # Invoice Join
    payment = data["payment"]
    assert payment["invoice_number"] == "INV-2026-0001"
    assert payment["payment_method"] == "Credit Card (Visa ending in 4242)"
    assert payment["payment_status"] == "PAID"
    assert payment["amount_paid"] == 367.19
    assert payment["is_invoice_found"] is True


@pytest.mark.asyncio
async def test_get_receipt_order_not_found(async_client: AsyncClient):
    response = await async_client.get("/api/v1/orders/ORD-NONEXISTENT-9999/receipt")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_get_receipt_missing_customer_profile_graceful_fallback(async_client: AsyncClient):
    response = await async_client.get("/api/v1/orders/ORD-5003/receipt")
    assert response.status_code == 200
    data = response.json()

    # Customer fallback
    customer = data["customer"]
    assert customer["user_id"] == "USER-GUEST-999"
    assert customer["is_profile_found"] is False
    assert customer["name"] == "Guest / Unregistered User"
    assert customer["shipping_address"] is None

    # Invoice still loaded
    assert data["payment"]["is_invoice_found"] is True
    assert data["payment"]["invoice_number"] == "INV-2026-0003"


@pytest.mark.asyncio
async def test_get_receipt_missing_invoice_graceful_fallback(async_client: AsyncClient):
    response = await async_client.get("/api/v1/orders/ORD-5004/receipt")
    assert response.status_code == 200
    data = response.json()

    # Customer loaded
    assert data["customer"]["is_profile_found"] is True
    assert data["customer"]["name"] == "Carol Danvers"

    # Payment fallback
    payment = data["payment"]
    assert payment["is_invoice_found"] is False
    assert payment["payment_status"] == "INVOICE_PENDING"
    assert payment["invoice_number"] is None
    assert payment["amount_paid"] == 0.0


@pytest.mark.asyncio
async def test_get_receipt_missing_product_graceful_fallback(async_client: AsyncClient):
    response = await async_client.get("/api/v1/orders/ORD-5005/receipt")
    assert response.status_code == 200
    data = response.json()

    items = data["items"]
    assert len(items) == 2

    # Normal product
    prod1 = next(item for item in items if item["product_id"] == "PROD-002")
    assert prod1["product_found"] is True
    assert prod1["title"] == "ApexType Mechanical Keyboard"

    # Missing/Legacy product
    prod2 = next(item for item in items if item["product_id"] == "PROD-LEGACY-404")
    assert prod2["product_found"] is False
    assert "Archived / Custom Item" in prod2["title"]
    assert prod2["total_price"] == 50.00
