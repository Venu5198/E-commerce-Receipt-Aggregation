from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: str = Field(default="customer", pattern="^(customer|admin|manager)$")


class UserLogin(BaseModel):
    username: str
    password: str


class UserModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    username: str
    email: EmailStr
    role: str = "customer"
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    username: str


class TokenData(BaseModel):
    user_id: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
