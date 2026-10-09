import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import get_db
from app.models.profile import (
    ProfileModel,
    ProfileCreate,
    ProfileUpdate,
    ProfileListResponse,
)

router = APIRouter(prefix="/api/v1/profiles", tags=["Profiles"])


def _find_profile_query(user_id: str):
    clean_id = user_id.strip()
    return {
        "$or": [
            {"user_id": clean_id},
            {"_id": clean_id},
        ]
    }


@router.post(
    "",
    response_model=ProfileModel,
    status_code=status.HTTP_201_CREATED,
    summary="Create Customer Profile",
)
async def create_profile(
    payload: ProfileCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    assigned_user_id = payload.user_id or f"USER-{uuid.uuid4().hex[:6].upper()}"

    # Check for existing profile with user_id or email
    existing = await db["profiles"].find_one({
        "$or": [
            {"user_id": assigned_user_id},
            {"email": payload.email},
        ]
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Profile with user_id '{assigned_user_id}' or email '{payload.email}' already exists.",
        )

    doc = {
        "_id": f"prof_{uuid.uuid4().hex[:8]}",
        "user_id": assigned_user_id,
        "full_name": payload.full_name,
        "email": payload.email,
        "phone": payload.phone,
        "address": payload.address.model_dump() if payload.address else None,
    }
    await db["profiles"].insert_one(doc)
    return ProfileModel(**doc)


@router.get(
    "",
    response_model=ProfileListResponse,
    summary="List Customer Profiles",
)
async def list_profiles(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cursor = db["profiles"].find().skip(skip).limit(limit)
    items = []
    async for doc in cursor:
        items.append(ProfileModel(**doc))
    total = await db["profiles"].count_documents({})
    return ProfileListResponse(total=total, items=items)


@router.get(
    "/{user_id}",
    response_model=ProfileModel,
    summary="Get Customer Profile",
)
async def get_profile(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    profile = await db["profiles"].find_one(_find_profile_query(user_id))
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{user_id}' not found.",
        )
    return ProfileModel(**profile)


@router.put(
    "/{user_id}",
    response_model=ProfileModel,
    summary="Update Profile (Full Replace)",
)
async def update_profile(
    user_id: str,
    payload: ProfileCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    profile = await db["profiles"].find_one(_find_profile_query(user_id))
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{user_id}' not found.",
        )

    update_doc = {
        "full_name": payload.full_name,
        "email": payload.email,
        "phone": payload.phone,
        "address": payload.address.model_dump() if payload.address else None,
    }
    await db["profiles"].update_one({"_id": profile["_id"]}, {"$set": update_doc})
    updated = await db["profiles"].find_one({"_id": profile["_id"]})
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{user_id}' not found.",
        )
    return ProfileModel(**updated)


@router.patch(
    "/{user_id}",
    response_model=ProfileModel,
    summary="Update Profile (Partial)",
)
async def patch_profile(
    user_id: str,
    payload: ProfileUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    profile = await db["profiles"].find_one(_find_profile_query(user_id))
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{user_id}' not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return ProfileModel(**profile)

    if "address" in update_data and update_data["address"] is not None:
        update_data["address"] = payload.address.model_dump()

    await db["profiles"].update_one({"_id": profile["_id"]}, {"$set": update_data})
    updated = await db["profiles"].find_one({"_id": profile["_id"]})
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{user_id}' not found.",
        )
    return ProfileModel(**updated)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Profile",
)
async def delete_profile(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    result = await db["profiles"].delete_one(_find_profile_query(user_id))
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile '{user_id}' not found.",
        )
    return None
