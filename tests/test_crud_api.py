import pytest
from httpx import AsyncClient


# ============================================================================
# Profiles CRUD Tests
# ============================================================================
@pytest.mark.asyncio
async def test_profile_crud_lifecycle(async_client: AsyncClient):
    # 1. Create Profile (POST)
    create_payload = {
        "user_id": "USER-9999",
        "full_name": "Test User",
        "email": "test.user@example.com",
        "phone": "+1-555-9999",
        "address": {
            "street": "123 Test Ave",
            "city": "Metropolis",
            "state": "NY",
            "postal_code": "10001",
            "country": "USA",
        },
    }
    res_post = await async_client.post("/api/v1/profiles", json=create_payload)
    assert res_post.status_code == 201
    created = res_post.json()
    assert created["user_id"] == "USER-9999"
    assert created["full_name"] == "Test User"

    # 2. Duplicate Check
    res_dup = await async_client.post("/api/v1/profiles", json=create_payload)
    assert res_dup.status_code == 409

    # 3. List Profiles (GET)
    res_list = await async_client.get("/api/v1/profiles?limit=10")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total"] >= 1
    assert any(p["user_id"] == "USER-9999" for p in list_data["items"])

    # 4. Get by ID (GET)
    res_get = await async_client.get("/api/v1/profiles/USER-9999")
    assert res_get.status_code == 200
    assert res_get.json()["email"] == "test.user@example.com"

    # 5. Full Update (PUT)
    put_payload = {
        "user_id": "USER-9999",
        "full_name": "Test User Updated",
        "email": "updated.user@example.com",
        "phone": "+1-555-0000",
        "address": {
            "street": "456 New St",
            "city": "Gotham",
            "state": "NJ",
            "postal_code": "07001",
            "country": "USA",
        },
    }
    res_put = await async_client.put("/api/v1/profiles/USER-9999", json=put_payload)
    assert res_put.status_code == 200
    assert res_put.json()["full_name"] == "Test User Updated"
    assert res_put.json()["email"] == "updated.user@example.com"

    # 6. Partial Update (PATCH)
    patch_payload = {"phone": "+1-555-8888"}
    res_patch = await async_client.patch("/api/v1/profiles/USER-9999", json=patch_payload)
    assert res_patch.status_code == 200
    assert res_patch.json()["phone"] == "+1-555-8888"
    assert res_patch.json()["full_name"] == "Test User Updated"

    # 7. Delete Profile (DELETE)
    res_del = await async_client.delete("/api/v1/profiles/USER-9999")
    assert res_del.status_code == 204

    # 8. Verify Gone (404)
    res_after = await async_client.get("/api/v1/profiles/USER-9999")
    assert res_after.status_code == 404


# ============================================================================
# Products CRUD Tests
# ============================================================================
@pytest.mark.asyncio
async def test_product_crud_lifecycle(async_client: AsyncClient):
    # 1. Create Product (POST)
    product_payload = {
        "product_id": "PROD-999",
        "sku": "TECH-TEST-99",
        "title": "Quantum Mechanical Keyboard",
        "description": "Ergonomic keyboard",
        "unit_price": 149.99,
        "currency": "USD",
        "category": "Electronics",
        "in_stock": True,
    }
    res_post = await async_client.post("/api/v1/products", json=product_payload)
    assert res_post.status_code == 201
    created = res_post.json()
    assert created["product_id"] == "PROD-999"
    assert created["sku"] == "TECH-TEST-99"

    # 2. List Products with Category Filter (GET)
    res_list = await async_client.get("/api/v1/products?category=Electronics")
    assert res_list.status_code == 200
    assert res_list.json()["total"] >= 1

    # 3. Get Product (GET)
    res_get = await async_client.get("/api/v1/products/PROD-999")
    assert res_get.status_code == 200
    assert res_get.json()["title"] == "Quantum Mechanical Keyboard"

    # 4. Full Update (PUT)
    put_payload = {
        "sku": "TECH-TEST-99-V2",
        "title": "Quantum Keyboard V2",
        "description": "Upgraded switch keyboard",
        "unit_price": 179.99,
        "currency": "USD",
        "category": "Peripherals",
        "in_stock": False,
    }
    res_put = await async_client.put("/api/v1/products/PROD-999", json=put_payload)
    assert res_put.status_code == 200
    assert res_put.json()["title"] == "Quantum Keyboard V2"
    assert res_put.json()["in_stock"] is False

    # 5. Partial Update (PATCH)
    res_patch = await async_client.patch(
        "/api/v1/products/PROD-999", json={"unit_price": 169.99, "in_stock": True}
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["unit_price"] == 169.99
    assert res_patch.json()["in_stock"] is True

    # 6. Delete Product (DELETE)
    res_del = await async_client.delete("/api/v1/products/PROD-999")
    assert res_del.status_code == 204

    # 7. Verify Gone (404)
    res_after = await async_client.get("/api/v1/products/PROD-999")
    assert res_after.status_code == 404


# ============================================================================
# Orders CRUD Tests
# ============================================================================
@pytest.mark.asyncio
async def test_order_crud_lifecycle(async_client: AsyncClient):
    # 1. Create Order (POST)
    order_payload = {
        "order_id": "ORD-9999",
        "user_id": "USER-1001",
        "status": "PROCESSING",
        "items": [
            {"product_id": "PROD-001", "quantity": 2, "unit_price": 100.0},
            {"product_id": "PROD-002", "quantity": 1, "unit_price": 50.0},
        ],
        "tax": 20.0,
        "shipping_fee": 10.0,
    }
    res_post = await async_client.post("/api/v1/orders", json=order_payload)
    assert res_post.status_code == 201
    created = res_post.json()
    assert created["order_id"] == "ORD-9999"
    # Auto-calculated amounts
    assert created["subtotal"] == 250.0  # (2*100 + 1*50)
    assert created["total_amount"] == 280.0  # 250 + 20 + 10

    # 2. List Orders (GET)
    res_list = await async_client.get("/api/v1/orders?user_id=USER-1001")
    assert res_list.status_code == 200
    assert res_list.json()["total"] >= 1

    # 3. Get Order (GET)
    res_get = await async_client.get("/api/v1/orders/ORD-9999")
    assert res_get.status_code == 200
    assert res_get.json()["status"] == "PROCESSING"

    # 4. Full Update (PUT)
    put_payload = {
        "user_id": "USER-1001",
        "status": "SHIPPED",
        "items": [{"product_id": "PROD-001", "quantity": 1, "unit_price": 100.0}],
        "tax": 10.0,
        "shipping_fee": 5.0,
    }
    res_put = await async_client.put("/api/v1/orders/ORD-9999", json=put_payload)
    assert res_put.status_code == 200
    assert res_put.json()["status"] == "SHIPPED"
    assert res_put.json()["total_amount"] == 115.0

    # 5. Partial Update (PATCH)
    res_patch = await async_client.patch(
        "/api/v1/orders/ORD-9999", json={"status": "DELIVERED"}
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["status"] == "DELIVERED"

    # 6. Delete Order (DELETE)
    res_del = await async_client.delete("/api/v1/orders/ORD-9999")
    assert res_del.status_code == 204

    # 7. Verify Gone (404)
    res_after = await async_client.get("/api/v1/orders/ORD-9999")
    assert res_after.status_code == 404


# ============================================================================
# Invoices CRUD Tests
# ============================================================================
@pytest.mark.asyncio
async def test_invoice_crud_lifecycle(async_client: AsyncClient):
    # 1. Create Invoice (POST)
    inv_payload = {
        "invoice_id": "INV-9999",
        "order_id": "ORD-5001",
        "invoice_number": "INV-NUM-9999",
        "payment_method": "CREDIT_CARD",
        "payment_status": "PAID",
        "amount_paid": 280.0,
        "transaction_id": "TXN_TEST_9999",
    }
    res_post = await async_client.post("/api/v1/invoices", json=inv_payload)
    assert res_post.status_code == 201
    created = res_post.json()
    assert created["invoice_id"] == "INV-9999"
    assert created["amount_paid"] == 280.0

    # 2. List Invoices (GET)
    res_list = await async_client.get("/api/v1/invoices?order_id=ORD-5001")
    assert res_list.status_code == 200
    assert res_list.json()["total"] >= 1

    # 3. Get Invoice (GET)
    res_get = await async_client.get("/api/v1/invoices/INV-9999")
    assert res_get.status_code == 200
    assert res_get.json()["payment_method"] == "CREDIT_CARD"

    # 4. Full Update (PUT)
    put_payload = {
        "order_id": "ORD-5001",
        "invoice_number": "INV-NUM-9999",
        "payment_method": "PAYPAL",
        "payment_status": "REFUNDED",
        "amount_paid": 280.0,
        "transaction_id": "TXN_REFUND_9999",
    }
    res_put = await async_client.put("/api/v1/invoices/INV-9999", json=put_payload)
    assert res_put.status_code == 200
    assert res_put.json()["payment_method"] == "PAYPAL"
    assert res_put.json()["payment_status"] == "REFUNDED"

    # 5. Partial Update (PATCH)
    res_patch = await async_client.patch(
        "/api/v1/invoices/INV-9999", json={"payment_status": "SETTLED"}
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["payment_status"] == "SETTLED"

    # 6. Delete Invoice (DELETE)
    res_del = await async_client.delete("/api/v1/invoices/INV-9999")
    assert res_del.status_code == 204

    # 7. Verify Gone (404)
    res_after = await async_client.get("/api/v1/invoices/INV-9999")
    assert res_after.status_code == 404
