import uuid
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import get_db
from app.models.order import (
    OrderModel,
    OrderCreate,
    OrderUpdate,
    OrderListResponse,
)
from app.services.cache_service import cache_service

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


def _find_order_query(order_id: str):
    clean_id = order_id.strip()
    return {
        "$or": [
            {"order_id": clean_id},
            {"_id": clean_id},
        ]
    }


@router.post(
    "",
    response_model=OrderModel,
    status_code=status.HTTP_201_CREATED,
    summary="Create Order",
)
async def create_order(
    payload: OrderCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    assigned_order_id = payload.order_id or f"ORD-{uuid.uuid4().hex[:6].upper()}"

    existing = await db["orders"].find_one({"order_id": assigned_order_id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order with ID '{assigned_order_id}' already exists.",
        )

    # Compute subtotal if not provided
    calculated_subtotal = payload.subtotal
    if calculated_subtotal is None:
        calculated_subtotal = round(
            sum(item.quantity * item.unit_price for item in payload.items), 2
        )

    calculated_total = payload.total_amount
    if calculated_total is None:
        calculated_total = round(
            calculated_subtotal + payload.tax + payload.shipping_fee, 2
        )

    doc = {
        "_id": f"ord_{uuid.uuid4().hex[:6]}",
        "order_id": assigned_order_id,
        "user_id": payload.user_id,
        "status": payload.status,
        "items": [item.model_dump() for item in payload.items],
        "subtotal": calculated_subtotal,
        "tax": payload.tax,
        "shipping_fee": payload.shipping_fee,
        "total_amount": calculated_total,
        "currency": payload.currency,
        "created_at": datetime.now(timezone.utc),
    }
    await db["orders"].insert_one(doc)
    return OrderModel(**doc)


@router.get(
    "",
    response_model=OrderListResponse,
    summary="List Orders",
)
async def list_orders(
    user_id: Optional[str] = None,
    order_status: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    filter_query = {}
    if user_id is not None:
        filter_query["user_id"] = user_id
    if order_status is not None:
        filter_query["status"] = order_status

    cursor = db["orders"].find(filter_query).skip(skip).limit(limit)
    items = []
    async for doc in cursor:
        items.append(OrderModel(**doc))
    total = await db["orders"].count_documents(filter_query)
    return OrderListResponse(total=total, items=items)


@router.get(
    "/{order_id}",
    response_model=OrderModel,
    summary="Get Order",
)
async def get_order(
    order_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    order = await db["orders"].find_one(_find_order_query(order_id))
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found.",
        )
    return OrderModel(**order)


@router.put(
    "/{order_id}",
    response_model=OrderModel,
    summary="Update Order (Full Replace)",
)
async def update_order(
    order_id: str,
    payload: OrderCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    order = await db["orders"].find_one(_find_order_query(order_id))
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found.",
        )

    calculated_subtotal = payload.subtotal
    if calculated_subtotal is None:
        calculated_subtotal = round(
            sum(item.quantity * item.unit_price for item in payload.items), 2
        )

    calculated_total = payload.total_amount
    if calculated_total is None:
        calculated_total = round(
            calculated_subtotal + payload.tax + payload.shipping_fee, 2
        )

    update_doc = {
        "user_id": payload.user_id,
        "status": payload.status,
        "items": [item.model_dump() for item in payload.items],
        "subtotal": calculated_subtotal,
        "tax": payload.tax,
        "shipping_fee": payload.shipping_fee,
        "total_amount": calculated_total,
        "currency": payload.currency,
    }
    await db["orders"].update_one({"_id": order["_id"]}, {"$set": update_doc})
    updated = await db["orders"].find_one({"_id": order["_id"]})
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found.",
        )
    await cache_service.delete(f"receipt:{order.get('order_id', order_id)}")
    return OrderModel(**updated)


@router.patch(
    "/{order_id}",
    response_model=OrderModel,
    summary="Update Order (Partial)",
)
async def patch_order(
    order_id: str,
    payload: OrderUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    order = await db["orders"].find_one(_find_order_query(order_id))
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return OrderModel(**order)

    if "items" in update_data and update_data["items"] is not None:
        update_data["items"] = [item.model_dump() for item in payload.items]

    await db["orders"].update_one({"_id": order["_id"]}, {"$set": update_data})
    updated = await db["orders"].find_one({"_id": order["_id"]})
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found.",
        )
    await cache_service.delete(f"receipt:{order.get('order_id', order_id)}")
    return OrderModel(**updated)


@router.delete(
    "/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Order",
)
async def delete_order(
    order_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    result = await db["orders"].delete_one(_find_order_query(order_id))
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found.",
        )
    await cache_service.delete(f"receipt:{order_id}")
    return None
