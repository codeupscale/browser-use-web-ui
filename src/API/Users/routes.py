# Update your existing routes.py - Add these imports and new routes

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from .current_user import get_current_user
from .schemas import (
    UserCreate, 
    UserLogin, 
    
    ResetPassword,
     # New import
)


from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .services import (
    create_user,
    login_user,
    reset_user_password,
    forgot_password_otp,
    update_password_with_otp
)

import logging
from jose import jwt, JWTError
import os
from dotenv import load_dotenv
from ..utils.env_loader import load_env_from_root

# Load environment variables from the root .env file
load_env_from_root()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

security = HTTPBearer()


router = APIRouter()
logger = logging.getLogger("user_routes")



@router.post("/signup")
async def signup(user: UserCreate):
    logger.info(f"Signup attempt for email: {user.email}")
    new_user = await create_user(user)
    return { "message": "User Created Successfully", "for": user.email}

@router.post("/login")
async def login(credentials: UserLogin):
    logger.info(f"Login attempt for email: {credentials.email}")
    token = login_user(credentials.email, credentials.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return JSONResponse(content={"access_token": token})

# sends otp to user's email
@router.post("/forgot-password")
async def forgot_password(email: str):
    """Updated to send OTP instead of token"""
    logger.info(f"Password reset OTP requested for email: {email}")
    success = await forgot_password_otp(email)
    if success:
        return JSONResponse(
            content={"message": "If your email is registered, you will receive an OTP shortly."},
            status_code=200
        )
    else:
        raise HTTPException(
            status_code=500, 
            detail="Failed to send OTP. Please try again later."
        )

#for users not logged in
@router.post("/reset-password-otp")
async def reset_password_with_otp(email: str, otp: str, new_password1: str, new_password2: str):
    """Reset password using verified OTP"""
    logger.info(f"Password reset with OTP requested for email: {email}")

    success = await update_password_with_otp(email, otp, new_password1, new_password2)
    if success:
        return JSONResponse(
            content={"message": "Password reset successful! You can now login with your new password."},
            status_code=200
        )
    else:
        raise HTTPException(
            status_code=400, 
            detail="Invalid or expired OTP, or password reset failed."
        )

# KEEP your existing reset-password route for backward compatibility
#for logged in users with no otp
@router.post("/reset-password", dependencies=[Depends(get_current_user)])
async def reset_password(data: ResetPassword, current_user: dict = Depends(get_current_user)):
    """Original token-based password reset - kept for backward compatibility"""
    logger.info(f"Password reset using token: {data.token}")
    await reset_user_password(data.token, data.new_password1, data.new_password2)
    return JSONResponse(content={"message": "Password reset successful."})
