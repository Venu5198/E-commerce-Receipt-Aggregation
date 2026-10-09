from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


class InvoiceCreate(BaseModel):
    invoice_id: Optional[str] = None
    order_id: str
    invoice_number: Optional[str] = None
    payment_method: str
    payment_status: str = "PAID"
    amount_paid: float
    currency: str = "USD"
    transaction_id: Optional[str] = None
    paid_at: Optional[datetime] = None


class InvoiceUpdate(BaseModel):
    order_id: Optional[str] = None
    invoice_number: Optional[str] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    amount_paid: Optional[float] = None
    currency: Optional[str] = None
    transaction_id: Optional[str] = None
    paid_at: Optional[datetime] = None


class InvoiceModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    invoice_id: str
    order_id: str
    invoice_number: str
    payment_method: str
    payment_status: str
    amount_paid: float
    currency: str = "USD"
    transaction_id: Optional[str] = None
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    paid_at: Optional[datetime] = None


class InvoiceListResponse(BaseModel):
    total: int
    items: List[InvoiceModel]
