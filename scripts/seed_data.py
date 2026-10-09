import asyncio
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import settings

PROFILES = [
    {
        "_id": "prof_1001",
        "user_id": "USER-1001",
        "full_name": "Alice Johnson",
        "email": "alice.johnson@example.com",
        "phone": "+1-555-0199",
        "address": {
            "street": "742 Evergreen Terrace",
            "city": "Springfield",
            "state": "OR",
            "postal_code": "97477",
            "country": "USA",
        },
    },
    {
        "_id": "prof_1002",
        "user_id": "USER-1002",
        "full_name": "Bob Smith",
        "email": "bob.smith@example.com",
        "phone": "+1-555-0288",
        "address": {
            "street": "221B Baker Street",
            "city": "London",
            "state": "Greater London",
            "postal_code": "NW1 6XE",
            "country": "UK",
        },
    },
    {
        "_id": "prof_1003",
        "user_id": "USER-1003",
        "full_name": "Carol Danvers",
        "email": "carol.danvers@example.com",
        "phone": "+1-555-0377",
        "address": {
            "street": "432 Park Avenue",
            "city": "New York",
            "state": "NY",
            "postal_code": "10022",
            "country": "USA",
        },
    },
]

PRODUCTS = [
    {
        "_id": "prod_001",
        "product_id": "PROD-001",
        "sku": "AUDIO-WNC-01",
        "title": "SonicQuiet Pro ANC Headphones",
        "description": "Wireless over-ear noise-canceling headphones with 40h battery life.",
        "unit_price": 249.99,
        "currency": "USD",
        "category": "Electronics",
        "in_stock": True,
    },
    {
        "_id": "prod_002",
        "product_id": "PROD-002",
        "sku": "KB-MECH-RGB",
        "title": "ApexType Mechanical Keyboard",
        "description": "Hot-swappable tactile RGB mechanical gaming keyboard.",
        "unit_price": 129.50,
        "currency": "USD",
        "category": "Peripherals",
        "in_stock": True,
    },
    {
        "_id": "prod_003",
        "product_id": "PROD-003",
        "sku": "MON-UW-34",
        "title": "VisionMax 34-Inch UltraWide Monitor",
        "description": "144Hz WQHD curved IPS productivity and gaming display.",
        "unit_price": 499.00,
        "currency": "USD",
        "category": "Displays",
        "in_stock": True,
    },
    {
        "_id": "prod_004",
        "product_id": "PROD-004",
        "sku": "HUB-USBC-7IN1",
        "title": "HyperPort 7-in-1 USB-C Hub",
        "description": "Aluminum USB-C multi-port adapter with 4K HDMI and 100W PD.",
        "unit_price": 45.00,
        "currency": "USD",
        "category": "Accessories",
        "in_stock": True,
    },
]

NOW = datetime.now(timezone.utc)

ORDERS = [
    {
        "_id": "ord_5001",
        "order_id": "ORD-5001",
        "user_id": "USER-1001",
        "status": "DELIVERED",
        "items": [
            {"product_id": "PROD-001", "quantity": 1, "unit_price": 249.99},
            {"product_id": "PROD-004", "quantity": 2, "unit_price": 45.00},
        ],
        "subtotal": 339.99,
        "tax": 27.20,
        "shipping_fee": 0.00,
        "total_amount": 367.19,
        "currency": "USD",
        "created_at": NOW - timedelta(days=5),
    },
    {
        "_id": "ord_5002",
        "order_id": "ORD-5002",
        "user_id": "USER-1002",
        "status": "PROCESSING",
        "items": [
            {"product_id": "PROD-002", "quantity": 1, "unit_price": 129.50},
            {"product_id": "PROD-003", "quantity": 1, "unit_price": 499.00},
        ],
        "subtotal": 628.50,
        "tax": 50.28,
        "shipping_fee": 15.00,
        "total_amount": 693.78,
        "currency": "USD",
        "created_at": NOW - timedelta(days=2),
    },
    {
        "_id": "ord_5003",
        "order_id": "ORD-5003",
        "user_id": "USER-GUEST-999",  # Edge Case: Profile does not exist
        "status": "SHIPPED",
        "items": [
            {"product_id": "PROD-001", "quantity": 1, "unit_price": 249.99},
        ],
        "subtotal": 249.99,
        "tax": 20.00,
        "shipping_fee": 10.00,
        "total_amount": 279.99,
        "currency": "USD",
        "created_at": NOW - timedelta(days=1),
    },
    {
        "_id": "ord_5004",
        "order_id": "ORD-5004",
        "user_id": "USER-1003",
        "status": "PENDING",  # Edge Case: Invoice not yet created
        "items": [
            {"product_id": "PROD-004", "quantity": 1, "unit_price": 45.00},
        ],
        "subtotal": 45.00,
        "tax": 3.60,
        "shipping_fee": 5.00,
        "total_amount": 53.60,
        "currency": "USD",
        "created_at": NOW - timedelta(hours=3),
    },
    {
        "_id": "ord_5005",
        "order_id": "ORD-5005",
        "user_id": "USER-1001",
        "status": "COMPLETED",
        "items": [
            {"product_id": "PROD-002", "quantity": 1, "unit_price": 129.50},
            {"product_id": "PROD-LEGACY-404", "quantity": 1, "unit_price": 50.00},  # Edge Case: Missing Product
        ],
        "subtotal": 179.50,
        "tax": 14.36,
        "shipping_fee": 0.00,
        "total_amount": 193.86,
        "currency": "USD",
        "created_at": NOW - timedelta(days=10),
    },
]

INVOICES = [
    {
        "_id": "inv_9001",
        "invoice_id": "INV-9001",
        "order_id": "ORD-5001",
        "invoice_number": "INV-2026-0001",
        "payment_method": "Credit Card (Visa ending in 4242)",
        "payment_status": "PAID",
        "amount_paid": 367.19,
        "currency": "USD",
        "transaction_id": "txn_stripe_abc123456",
        "issued_at": NOW - timedelta(days=5),
        "paid_at": NOW - timedelta(days=5),
    },
    {
        "_id": "inv_9002",
        "invoice_id": "INV-9002",
        "order_id": "ORD-5002",
        "invoice_number": "INV-2026-0002",
        "payment_method": "PayPal (bob.smith@example.com)",
        "payment_status": "PAID",
        "amount_paid": 693.78,
        "currency": "USD",
        "transaction_id": "txn_paypal_xyz987654",
        "issued_at": NOW - timedelta(days=2),
        "paid_at": NOW - timedelta(days=2),
    },
    {
        "_id": "inv_9003",
        "invoice_id": "INV-9003",
        "order_id": "ORD-5003",
        "invoice_number": "INV-2026-0003",
        "payment_method": "Apple Pay",
        "payment_status": "PAID",
        "amount_paid": 279.99,
        "currency": "USD",
        "transaction_id": "txn_apple_555666777",
        "issued_at": NOW - timedelta(days=1),
        "paid_at": NOW - timedelta(days=1),
    },
    {
        "_id": "inv_9005",
        "invoice_id": "INV-9005",
        "order_id": "ORD-5005",
        "invoice_number": "INV-2026-0005",
        "payment_method": "Debit Card (Mastercard ending in 9012)",
        "payment_status": "PAID",
        "amount_paid": 193.86,
        "currency": "USD",
        "transaction_id": "txn_mc_111222333",
        "issued_at": NOW - timedelta(days=10),
        "paid_at": NOW - timedelta(days=10),
    },
]


async def seed():
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB_NAME]

    print(f"Connecting to MongoDB at {settings.MONGO_URI}, DB: '{settings.MONGO_DB_NAME}'...")

    # Clear existing collections
    for coll_name in ["profiles", "products", "orders", "invoices"]:
        await db[coll_name].delete_many({})
        print(f"Cleared '{coll_name}' collection.")

    # Insert data
    await db["profiles"].insert_many(PROFILES)
    print(f"Inserted {len(PROFILES)} profiles.")

    await db["products"].insert_many(PRODUCTS)
    print(f"Inserted {len(PRODUCTS)} products.")

    await db["orders"].insert_many(ORDERS)
    print(f"Inserted {len(ORDERS)} orders.")

    await db["invoices"].insert_many(INVOICES)
    print(f"Inserted {len(INVOICES)} invoices.")

    # Create Indexes for fast querying
    await db["profiles"].create_index("user_id", unique=True)
    await db["products"].create_index("product_id", unique=True)
    await db["orders"].create_index("order_id", unique=True)
    await db["invoices"].create_index("order_id")

    print("\nDatabase seeded successfully!")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
