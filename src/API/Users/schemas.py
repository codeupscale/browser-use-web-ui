

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from enum import Enum
from .models import UserRole, UserStatus
from datetime import datetime

# Schema for user creation
class UserCreate(BaseModel):
    firstname: str = Field(..., min_length=1)
    lastname: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=6)
    organization: Optional[str] = None
    role: UserRole = UserRole.viewer
    status: UserStatus = UserStatus.active

# schema for user login
class UserLogin(BaseModel):
    email: EmailStr
    password: str


#used for /reset-password route
class ResetPassword(BaseModel):
    token: str  # Or OTP/token from token
    new_password1: str = Field(..., min_length=6)
    new_password2: str = Field(..., min_length=6)


  # Optional timestamp for OTP creation
