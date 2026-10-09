import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from mongomock_motor import AsyncMongoMockClient
from app.main import app
from app.db import get_db
from scripts.seed_data import PROFILES, PRODUCTS, ORDERS, INVOICES


@pytest_asyncio.fixture
async def mock_db():
    client = AsyncMongoMockClient()
    db = client["test_ecommerce_receipts"]

    # Seed mock database
    await db["profiles"].insert_many([p.copy() for p in PROFILES])
    await db["products"].insert_many([p.copy() for p in PRODUCTS])
    await db["orders"].insert_many([o.copy() for o in ORDERS])
    await db["invoices"].insert_many([i.copy() for i in INVOICES])

    yield db
    client.close()


@pytest_asyncio.fixture
async def async_client(mock_db):
    async def override_get_db():
        return mock_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
