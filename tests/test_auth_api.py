import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_register_and_login_lifecycle(async_client: AsyncClient):
    # 1. Register a customer user
    register_payload = {
        "username": "alice_dev",
        "email": "alice@example.com",
        "password": "Password123!",
        "role": "customer",
    }
    reg_resp = await async_client.post("/api/v1/auth/register", json=register_payload)
    assert reg_resp.status_code == 201, reg_resp.text
    reg_data = reg_resp.json()
    assert "access_token" in reg_data
    assert reg_data["role"] == "customer"
    assert reg_data["username"] == "alice_dev"

    customer_token = reg_data["access_token"]

    # 2. Prevent duplicate registration
    dup_resp = await async_client.post("/api/v1/auth/register", json=register_payload)
    assert dup_resp.status_code == 409

    # 3. Login with correct credentials
    login_payload = {
        "username": "alice_dev",
        "password": "Password123!",
    }
    login_resp = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "access_token" in login_data
    assert login_data["username"] == "alice_dev"

    # 4. Login with invalid password
    bad_login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "alice_dev", "password": "WrongPassword!"},
    )
    assert bad_login_resp.status_code == 401

    # 5. Access /api/v1/auth/me with Bearer token
    me_resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["username"] == "alice_dev"
    assert me_data["email"] == "alice@example.com"
    assert me_data["role"] == "customer"

    # 6. Access /api/v1/auth/me without token
    unauth_resp = await async_client.get("/api/v1/auth/me")
    assert unauth_resp.status_code in (401, 403)

    # 7. Customer user denied access to admin-only endpoint (403 Forbidden)
    forbidden_resp = await async_client.get(
        "/api/v1/auth/admin-only",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert forbidden_resp.status_code == 403

    # 8. Register an admin user and access admin-only endpoint (200 OK)
    admin_payload = {
        "username": "admin_boss",
        "email": "boss@example.com",
        "password": "AdminPassword123!",
        "role": "admin",
    }
    admin_reg_resp = await async_client.post("/api/v1/auth/register", json=admin_payload)
    assert admin_reg_resp.status_code == 201
    admin_token = admin_reg_resp.json()["access_token"]

    admin_resp = await async_client.get(
        "/api/v1/auth/admin-only",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_resp.status_code == 200
    assert admin_resp.json()["status"] == "authorized"
    assert admin_resp.json()["username"] == "admin_boss"
