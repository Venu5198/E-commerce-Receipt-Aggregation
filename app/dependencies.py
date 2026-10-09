from typing import Callable, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db import get_db
from app.models.user import UserModel
from app.security import decode_access_token

security_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> UserModel:
    token = credentials.credentials
    payload = decode_access_token(token)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db["users"].find_one({"_id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserModel(**user)


def require_role(allowed_roles: List[str]) -> Callable:
    async def role_checker(
        current_user: UserModel = Depends(get_current_user),
    ) -> UserModel:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {', '.join(allowed_roles)}.",
            )
        return current_user

    return role_checker
