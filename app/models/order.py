from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


class OrderItem(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0.0)


class OrderCreate(BaseModel):
    order_id: Optional[str] = None
    user_id: str
    status: str = "PENDING"
    items: List[OrderItem]
    subtotal: Optional[float] = None
    tax: float = 0.0
    shipping_fee: float = 0.0
    total_amount: Optional[float] = None
    currency: str = "USD"


class OrderUpdate(BaseModel):
    user_id: Optional[str] = None
    status: Optional[str] = None
    items: Optional[List[OrderItem]] = None
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    shipping_fee: Optional[float] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None


class OrderModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    order_id: str
    user_id: str
    status: str
    items: List[OrderItem]
    subtotal: float
    tax: float = 0.0
    shipping_fee: float = 0.0
    total_amount: float
    currency: str = "USD"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderListResponse(BaseModel):
    total: int
    items: List[OrderModel]
