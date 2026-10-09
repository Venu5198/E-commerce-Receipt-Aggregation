import re
from typing import Dict, Any, List
from datetime import datetime, timezone
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.receipt import (
    ReceiptResponse,
    CustomerInfo,
    ReceiptItem,
    ReceiptSummary,
    PaymentInfo,
)
from app.models.profile import Address
from app.services.cache_service import cache_service


class ReceiptService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def invalidate_receipt(self, order_id: str) -> None:
        clean_id = order_id.strip()
        await cache_service.delete(f"receipt:{clean_id}")

    async def get_receipt(self, order_id: str) -> ReceiptResponse:
        clean_id = order_id.strip()

        # Check Cache
        cached_receipt = await cache_service.get(f"receipt:{clean_id}")
        if cached_receipt:
            return cached_receipt

        # 1. Fetch Order (Supports ORD-5001, ord_5001, 5001, or case-insensitive)
        order = await self.db["orders"].find_one({
            "$or": [
                {"order_id": clean_id},
                {"_id": clean_id},
                {"order_id": f"ORD-{clean_id}"},
                {"_id": f"ord_{clean_id}"},
                {"order_id": {"$regex": f"^{re.escape(clean_id)}$", "$options": "i"}},
            ]
        })

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order with ID '{order_id}' was not found. Valid seeded IDs: ORD-5001, ORD-5002, ORD-5003, ORD-5004, ORD-5005 (or numeric: 5001-5005).",
            )

        resolved_order_id = order.get("order_id", str(order.get("_id", clean_id)))
        user_id = order.get("user_id")
        order_items_raw: List[Dict[str, Any]] = order.get("items", [])

        # 2. Extract product IDs and Batch Query (Eliminating N+1 queries)
        product_ids = [item.get("product_id") for item in order_items_raw if item.get("product_id")]
        
        products_map: Dict[str, Dict[str, Any]] = {}
        if product_ids:
            cursor = self.db["products"].find({
                "$or": [
                    {"product_id": {"$in": product_ids}},
                    {"_id": {"$in": product_ids}}
                ]
            })
            async for prod in cursor:
                p_key1 = prod.get("product_id")
                p_key2 = str(prod.get("_id"))
                if p_key1:
                    products_map[p_key1] = prod
                if p_key2:
                    products_map[p_key2] = prod

        # 3. Fetch Customer Profile (Handled gracefully if missing)
        customer_info = CustomerInfo(user_id=user_id or "UNKNOWN")
        if user_id:
            profile = await self.db["profiles"].find_one({
                "$or": [{"user_id": user_id}, {"_id": user_id}]
            })
            if profile:
                addr_data = profile.get("address")
                address = Address(**addr_data) if isinstance(addr_data, dict) else None
                customer_info = CustomerInfo(
                    user_id=user_id,
                    name=profile.get("full_name", "Valued Customer"),
                    email=profile.get("email"),
                    phone=profile.get("phone"),
                    shipping_address=address,
                    is_profile_found=True,
                )
            else:
                customer_info.is_profile_found = False
                customer_info.name = "Guest / Unregistered User"
        else:
            customer_info.is_profile_found = False
            customer_info.name = "Guest Customer"

        # 4. Fetch Invoice (Handled gracefully if missing)
        invoice = await self.db["invoices"].find_one({
            "$or": [
                {"order_id": resolved_order_id},
                {"order_id": order_id},
                {"order_id": f"ORD-{clean_id}"},
                {"order_id": clean_id}
            ]
        })

        if invoice:
            payment_info = PaymentInfo(
                invoice_number=invoice.get("invoice_number"),
                payment_method=invoice.get("payment_method"),
                payment_status=invoice.get("payment_status", "PAID"),
                amount_paid=float(invoice.get("amount_paid", 0.0)),
                paid_at=invoice.get("paid_at") or invoice.get("issued_at"),
                is_invoice_found=True,
            )
        else:
            payment_info = PaymentInfo(
                invoice_number=None,
                payment_method=None,
                payment_status="INVOICE_PENDING",
                amount_paid=0.0,
                paid_at=None,
                is_invoice_found=False,
            )

        # 5. Build Item List with joined Product Details
        receipt_items: List[ReceiptItem] = []
        for raw_item in order_items_raw:
            pid = raw_item.get("product_id", "")
            qty = int(raw_item.get("quantity", 1))
            unit_price = float(raw_item.get("unit_price", 0.0))
            total_price = round(qty * unit_price, 2)

            prod_doc = products_map.get(pid)
            if prod_doc:
                receipt_items.append(
                    ReceiptItem(
                        product_id=pid,
                        title=prod_doc.get("title", "Product"),
                        sku=prod_doc.get("sku"),
                        category=prod_doc.get("category"),
                        quantity=qty,
                        unit_price=unit_price,
                        total_price=total_price,
                        product_found=True,
                    )
                )
            else:
                receipt_items.append(
                    ReceiptItem(
                        product_id=pid,
                        title=f"Archived / Custom Item ({pid})",
                        sku=None,
                        category=None,
                        quantity=qty,
                        unit_price=unit_price,
                        total_price=total_price,
                        product_found=False,
                    )
                )

        # 6. Build Summary
        currency = order.get("currency", "USD")
        subtotal = float(order.get("subtotal", sum(item.total_price for item in receipt_items)))
        tax = float(order.get("tax", 0.0))
        shipping_fee = float(order.get("shipping_fee", 0.0))
        total_amount = float(order.get("total_amount", round(subtotal + tax + shipping_fee, 2)))

        summary = ReceiptSummary(
            subtotal=round(subtotal, 2),
            tax=round(tax, 2),
            shipping_fee=round(shipping_fee, 2),
            total_amount=round(total_amount, 2),
            currency=currency,
        )

        order_date = order.get("created_at")
        if isinstance(order_date, str):
            try:
                order_date = datetime.fromisoformat(order_date)
            except ValueError:
                order_date = datetime.now(timezone.utc)
        elif not isinstance(order_date, datetime):
            order_date = datetime.now(timezone.utc)

        receipt_obj = ReceiptResponse(
            receipt_id=f"REC-{resolved_order_id}",
            order_id=resolved_order_id,
            order_status=order.get("status", "COMPLETED"),
            order_date=order_date,
            customer=customer_info,
            items=receipt_items,
            summary=summary,
            payment=payment_info,
            generated_at=datetime.now(timezone.utc),
        )

        # Store in cache with 60-second TTL
        await cache_service.set(f"receipt:{clean_id}", receipt_obj, ttl_seconds=60)
        return receipt_obj
