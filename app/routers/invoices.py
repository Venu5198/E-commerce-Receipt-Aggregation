import uuid
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import get_db
from app.models.invoice import (
    InvoiceModel,
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceListResponse,
)
from app.services.cache_service import cache_service

router = APIRouter(prefix="/api/v1/invoices", tags=["Invoices"])


def _find_invoice_query(invoice_id: str):
    clean_id = invoice_id.strip()
    return {
        "$or": [
            {"invoice_id": clean_id},
            {"_id": clean_id},
            {"invoice_number": clean_id},
        ]
    }


@router.post(
    "",
    response_model=InvoiceModel,
    status_code=status.HTTP_201_CREATED,
    summary="Create Invoice",
)
async def create_invoice(
    payload: InvoiceCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    assigned_invoice_id = payload.invoice_id or f"INV-{uuid.uuid4().hex[:6].upper()}"
    assigned_invoice_num = (
        payload.invoice_number or f"INV-NUM-{uuid.uuid4().hex[:6].upper()}"
    )

    existing = await db["invoices"].find_one({
        "$or": [
            {"invoice_id": assigned_invoice_id},
            {"invoice_number": assigned_invoice_num},
        ]
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice '{assigned_invoice_id}' already exists.",
        )

    doc = {
        "_id": f"inv_{uuid.uuid4().hex[:6]}",
        "invoice_id": assigned_invoice_id,
        "order_id": payload.order_id,
        "invoice_number": assigned_invoice_num,
        "payment_method": payload.payment_method,
        "payment_status": payload.payment_status,
        "amount_paid": payload.amount_paid,
        "currency": payload.currency,
        "transaction_id": payload.transaction_id,
        "issued_at": datetime.now(timezone.utc),
        "paid_at": payload.paid_at,
    }
    await db["invoices"].insert_one(doc)
    return InvoiceModel(**doc)


@router.get(
    "",
    response_model=InvoiceListResponse,
    summary="List Invoices",
)
async def list_invoices(
    order_id: Optional[str] = None,
    payment_status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    filter_query = {}
    if order_id is not None:
        filter_query["order_id"] = order_id
    if payment_status is not None:
        filter_query["payment_status"] = payment_status

    cursor = db["invoices"].find(filter_query).skip(skip).limit(limit)
    items = []
    async for doc in cursor:
        items.append(InvoiceModel(**doc))
    total = await db["invoices"].count_documents(filter_query)
    return InvoiceListResponse(total=total, items=items)


@router.get(
    "/{invoice_id}",
    response_model=InvoiceModel,
    summary="Get Invoice",
)
async def get_invoice(
    invoice_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    invoice = await db["invoices"].find_one(_find_invoice_query(invoice_id))
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_id}' not found.",
        )
    return InvoiceModel(**invoice)


@router.put(
    "/{invoice_id}",
    response_model=InvoiceModel,
    summary="Update Invoice (Full Replace)",
)
async def update_invoice(
    invoice_id: str,
    payload: InvoiceCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    invoice = await db["invoices"].find_one(_find_invoice_query(invoice_id))
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_id}' not found.",
        )

    update_doc = {
        "order_id": payload.order_id,
        "invoice_number": payload.invoice_number or invoice.get("invoice_number"),
        "payment_method": payload.payment_method,
        "payment_status": payload.payment_status,
        "amount_paid": payload.amount_paid,
        "currency": payload.currency,
        "transaction_id": payload.transaction_id,
        "paid_at": payload.paid_at,
    }
    await db["invoices"].update_one({"_id": invoice["_id"]}, {"$set": update_doc})
    updated = await db["invoices"].find_one({"_id": invoice["_id"]})
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_id}' not found.",
        )
    if "order_id" in invoice:
        await cache_service.delete(f"receipt:{invoice['order_id']}")
    return InvoiceModel(**updated)


@router.patch(
    "/{invoice_id}",
    response_model=InvoiceModel,
    summary="Update Invoice (Partial)",
)
async def patch_invoice(
    invoice_id: str,
    payload: InvoiceUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    invoice = await db["invoices"].find_one(_find_invoice_query(invoice_id))
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_id}' not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return InvoiceModel(**invoice)

    await db["invoices"].update_one({"_id": invoice["_id"]}, {"$set": update_data})
    updated = await db["invoices"].find_one({"_id": invoice["_id"]})
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_id}' not found.",
        )
    if "order_id" in invoice:
        await cache_service.delete(f"receipt:{invoice['order_id']}")
    return InvoiceModel(**updated)


@router.delete(
    "/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Invoice",
)
async def delete_invoice(
    invoice_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    invoice = await db["invoices"].find_one(_find_invoice_query(invoice_id))
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_id}' not found.",
        )
    await db["invoices"].delete_one({"_id": invoice["_id"]})
    if "order_id" in invoice:
        await cache_service.delete(f"receipt:{invoice['order_id']}")
    return None
