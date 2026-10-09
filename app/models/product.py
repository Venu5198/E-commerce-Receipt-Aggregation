from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ProductCreate(BaseModel):
    product_id: Optional[str] = None
    sku: str
    title: str
    description: Optional[str] = None
    unit_price: float = Field(gt=0.0)
    currency: str = "USD"
    category: Optional[str] = None
    in_stock: bool = True


class ProductUpdate(BaseModel):
    sku: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    unit_price: Optional[float] = Field(default=None, gt=0.0)
    currency: Optional[str] = None
    category: Optional[str] = None
    in_stock: Optional[bool] = None


class ProductModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    product_id: str
    sku: str
    title: str
    description: Optional[str] = None
    unit_price: float
    currency: str = "USD"
    category: Optional[str] = None
    in_stock: bool = True


class ProductListResponse(BaseModel):
    total: int
    items: List[ProductModel]
