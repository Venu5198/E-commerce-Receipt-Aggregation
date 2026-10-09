from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class Address(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class ProfileCreate(BaseModel):
    user_id: Optional[str] = None
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[Address] = None


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[Address] = None


class ProfileModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    user_id: str
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[Address] = None


class ProfileListResponse(BaseModel):
    total: int
    items: List[ProfileModel]
