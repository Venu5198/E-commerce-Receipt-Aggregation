import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import get_db
from app.dependencies import get_current_user, require_role
from app.models.user import (
    UserRegister,
    UserLogin,
    UserModel,
    TokenResponse,
)
from app.security import (
    hash_password,
    verify_password,
    create_access_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & Authorization"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    payload: UserRegister,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    existing = await db["users"].find_one({
        "$or": [
            {"username": payload.username.lower()},
            {"email": payload.email.lower()},
        ]
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this username or email already exists.",
        )

    user_id = f"usr_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    hashed = hash_password(payload.password)

    user_doc = {
        "_id": user_id,
        "username": payload.username.lower(),
        "email": payload.email.lower(),
        "role": payload.role,
        "hashed_password": hashed,
        "created_at": now_iso,
    }
    await db["users"].insert_one(user_doc)

    token = create_access_token({
        "sub": user_id,
        "username": user_doc["username"],
        "role": user_doc["role"],
    })

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user_doc["role"],
        user_id=user_id,
        username=user_doc["username"],
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain JWT token",
)
async def login(
    payload: UserLogin,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    identifier = payload.username.lower().strip()
    user = await db["users"].find_one({
        "$or": [
            {"username": identifier},
            {"email": identifier},
        ]
    })

    if not user or not verify_password(payload.password, user.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({
        "sub": user["_id"],
        "username": user["username"],
        "role": user["role"],
    })

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user["role"],
        user_id=user["_id"],
        username=user["username"],
    )


@router.get(
    "/me",
    response_model=UserModel,
    summary="Get current authenticated user profile",
)
async def get_me(
    current_user: UserModel = Depends(get_current_user),
):
    return current_user


@router.get(
    "/admin-only",
    summary="Example endpoint accessible only by admin role",
)
async def admin_only_route(
    current_user: UserModel = Depends(require_role(["admin"])),
):
    return {
        "status": "authorized",
        "message": "Welcome, Administrator.",
        "username": current_user.username,
        "role": current_user.role,
    }
