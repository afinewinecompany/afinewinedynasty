from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class User(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    google_id: Optional[str] = None
    profile_picture: Optional[str] = None
    subscription_tier: str = "free"  # free, premium, enterprise


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserInDB(User):
    hashed_password: str


class UserAuth(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    id: int
    email: EmailStr
    hashed_password: str
    is_active: bool
    subscription_tier: str = "free"