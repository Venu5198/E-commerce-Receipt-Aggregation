from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from app.models.profile import Address


class CustomerInfo(BaseModel):
    user_id: str
    name: str = "Unknown Customer"
    email: Optional[str] = None
    phone: Optional[str] = None
    shipping_address: Optional[Address] = None
    is_profile_found: bool = True


class ReceiptItem(BaseModel):
    product_id: str
    title: str = "Unlisted Product"
    sku: Optional[str] = None
    category: Optional[str] = None
    quantity: int
    unit_price: float
    total_price: float
    product_found: bool = True


class ReceiptSummary(BaseModel):
    subtotal: float
    tax: float
    shipping_fee: float
    total_amount: float
    currency: str


class PaymentInfo(BaseModel):
    invoice_number: Optional[str] = None
    payment_method: Optional[str] = None
    payment_status: str = "UNPAID"
    amount_paid: float = 0.0
    paid_at: Optional[datetime] = None
    is_invoice_found: bool = True


class ReceiptResponse(BaseModel):
    receipt_id: str
    order_id: str
    order_status: str
    order_date: datetime
    customer: CustomerInfo
    items: List[ReceiptItem]
    summary: ReceiptSummary
    payment: PaymentInfo
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
