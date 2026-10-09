import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("api.notifications")


class NotificationService:
    """Asynchronous background dispatcher for notifications, emails, and audit logs."""

    @staticmethod
    async def dispatch_receipt_email(
        db: AsyncIOMotorDatabase,
        order_id: str,
        recipient_email: str,
        total_amount: float,
        currency: str,
    ) -> Dict[str, Any]:
        """Simulates asynchronous non-blocking email dispatch and persists an audit log record."""
        # Non-blocking async simulation (0.05s)
        await asyncio.sleep(0.05)

        log_entry = {
            "event": "RECEIPT_DISPATCHED",
            "order_id": order_id,
            "recipient_email": recipient_email,
            "total_amount": total_amount,
            "currency": currency,
            "status": "SENT",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Store in audit_logs collection for compliance and auditing
        try:
            await db["audit_logs"].insert_one(log_entry.copy())
        except Exception as e:
            logger.error("Failed to write audit log: %s", e)

        logger.info(
            '{"event": "RECEIPT_EMAIL_SENT", "order_id": "%s", "recipient": "%s"}',
            order_id,
            recipient_email,
        )

        # Broadcast event across message broker
        from app.services.event_bus import event_bus
        await event_bus.publish("receipt.dispatched", log_entry)

        return log_entry


notification_service = NotificationService()
