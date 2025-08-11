#
# from beanie import Document
from pydantic import EmailStr, Field, BaseModel
from typing import Optional
from enum import Enum
from .dt import  DatetimeUtil
from datetime import datetime , timezone

class UserRole(str, Enum):
    viewer = "viewer"
    admin = "admin"
    qa_engineer = "QA engineer"
    developer = "developer"


class UserStatus(str, Enum):
    active = "active"
    inactive = "inactive"


#user model for db interaction   
class UserModel(BaseModel):
    firstname: str
    lastname: str
    email: EmailStr
    hashed_password: str
    organization: Optional[str] = None
    role: UserRole = UserRole.viewer
    status: UserStatus = UserStatus.active
    timetrack: DatetimeUtil = Field(default_factory=DatetimeUtil)
    otp :  Optional[str]
    otp_created_at: Optional[datetime]
    
  