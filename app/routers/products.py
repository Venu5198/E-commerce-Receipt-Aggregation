import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import get_db
from app.models.product import (
    ProductModel,
    ProductCreate,
    ProductUpdate,
    ProductListResponse,
)

router = APIRouter(prefix="/api/v1/products", tags=["Products"])


def _find_product_query(product_id: str):
    clean_id = product_id.strip()
    return {
        "$or": [
            {"product_id": clean_id},
            {"_id": clean_id},
        ]
    }


@router.post(
    "",
    response_model=ProductModel,
    status_code=status.HTTP_201_CREATED,
    summary="Create Product",
)
async def create_product(
    payload: ProductCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    assigned_prod_id = payload.product_id or f"PROD-{uuid.uuid4().hex[:4].upper()}"

    existing = await db["products"].find_one({
        "$or": [
            {"product_id": assigned_prod_id},
            {"sku": payload.sku},
        ]
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with ID '{assigned_prod_id}' or SKU '{payload.sku}' already exists.",
        )

    doc = {
        "_id": f"prod_{uuid.uuid4().hex[:6]}",
        "product_id": assigned_prod_id,
        "sku": payload.sku,
        "title": payload.title,
        "description": payload.description,
        "unit_price": payload.unit_price,
        "currency": payload.currency,
        "category": payload.category,
        "in_stock": payload.in_stock,
    }
    await db["products"].insert_one(doc)
    return ProductModel(**doc)


@router.get(
    "",
    response_model=ProductListResponse,
    summary="List Products",
)
async def list_products(
    category: Optional[str] = None,
    in_stock: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    filter_query = {}
    if category is not None:
        filter_query["category"] = category
    if in_stock is not None:
        filter_query["in_stock"] = in_stock

    cursor = db["products"].find(filter_query).skip(skip).limit(limit)
    items = []
    async for doc in cursor:
        items.append(ProductModel(**doc))
    total = await db["products"].count_documents(filter_query)
    return ProductListResponse(total=total, items=items)


@router.get(
    "/{product_id}",
    response_model=ProductModel,
    summary="Get Product",
)
async def get_product(
    product_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    product = await db["products"].find_one(_find_product_query(product_id))
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found.",
        )
    return ProductModel(**product)


@router.put(
    "/{product_id}",
    response_model=ProductModel,
    summary="Update Product (Full Replace)",
)
async def update_product(
    product_id: str,
    payload: ProductCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    product = await db["products"].find_one(_find_product_query(product_id))
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found.",
        )

    update_doc = {
        "sku": payload.sku,
        "title": payload.title,
        "description": payload.description,
        "unit_price": payload.unit_price,
        "currency": payload.currency,
        "category": payload.category,
        "in_stock": payload.in_stock,
    }
    await db["products"].update_one({"_id": product["_id"]}, {"$set": update_doc})
    updated = await db["products"].find_one({"_id": product["_id"]})
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found.",
        )
    return ProductModel(**updated)


@router.patch(
    "/{product_id}",
    response_model=ProductModel,
    summary="Update Product (Partial)",
)
async def patch_product(
    product_id: str,
    payload: ProductUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    product = await db["products"].find_one(_find_product_query(product_id))
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return ProductModel(**product)

    await db["products"].update_one({"_id": product["_id"]}, {"$set": update_data})
    updated = await db["products"].find_one({"_id": product["_id"]})
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found.",
        )
    return ProductModel(**updated)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Product",
)
async def delete_product(
    product_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    result = await db["products"].delete_one(_find_product_query(product_id))
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found.",
        )
    return None
