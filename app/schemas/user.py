from pydantic import BaseModel, EmailStr
from typing import Optional


class UserBase(BaseModel):
    username: str
    email: EmailStr
    role: str
    phone: str


class UserCreate(UserBase):
    password: str
    full_name: Optional[str] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class UserRead(UserBase):
    id: int
    full_name: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True
