from fastapi import APIRouter, BackgroundTasks, Depends, Path, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import get_db
from app.services.receipt_service import ReceiptService
from app.services.notification_service import notification_service
from app.models.receipt import ReceiptResponse

router = APIRouter(prefix="/api/v1/orders", tags=["Receipts"])


@router.get(
    "/{order_id}/receipt",
    response_model=ReceiptResponse,
    summary="Get Aggregated Order Receipt",
    description="Aggregates order details, customer profile, batch product metadata, and invoice payment confirmation. Cached for fast sub-millisecond retrieval.",
    responses={
        200: {"description": "Receipt successfully generated and aggregated."},
        404: {"description": "Order not found."},
    },
)
async def get_order_receipt(
    order_id: str = Path(..., description="Unique Order ID or Document ID"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ReceiptResponse:
    service = ReceiptService(db)
    return await service.get_receipt(order_id)


@router.post(
    "/{order_id}/receipt/dispatch",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Dispatch Receipt Email (Async Background Job)",
    description="Schedules non-blocking asynchronous email delivery and audit logging in the background.",
)
async def dispatch_receipt_async(
    order_id: str = Path(..., description="Order ID to dispatch receipt for"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    service = ReceiptService(db)
    receipt = await service.get_receipt(order_id)

    recipient = receipt.customer.email or "customer@example.com"
    background_tasks.add_task(
        notification_service.dispatch_receipt_email,
        db,
        receipt.order_id,
        recipient,
        receipt.summary.total_amount,
        receipt.summary.currency,
    )

    return {
        "status": "queued",
        "message": f"Receipt dispatch background job scheduled for order '{receipt.order_id}'.",
        "recipient": recipient,
        "receipt_id": receipt.receipt_id,
    }
