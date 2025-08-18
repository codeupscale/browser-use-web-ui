
from typing import Optional
from fastapi import HTTPException
from jose import jwt, JWTError
from random import randint
import logging
from datetime import datetime, timezone
from ..db.db_connection import get_db, close_db
from ..Users.models import UserModel
import re, os
from fastapi import HTTPException
from dotenv import load_dotenv
from ..utils.env_loader import load_env_from_root

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType


from dateutil import parser
# Load environment variables from the root .env file
load_env_from_root()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "300"))
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@example.com")
EMAIL_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")

# Only create ConnectionConfig if email credentials are available
conf = None
if EMAIL_USERNAME and EMAIL_PASSWORD:
    conf = ConnectionConfig(
        MAIL_USERNAME=EMAIL_USERNAME,
        MAIL_PASSWORD=EMAIL_PASSWORD,
        MAIL_FROM=EMAIL_FROM,
        MAIL_PORT=EMAIL_PORT,
        MAIL_SERVER=EMAIL_SERVER,
        USE_CREDENTIALS=True,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
    )
# Logger setup
logger = logging.getLogger("security")
logging.basicConfig(level=logging.INFO)


def verify_reset_token(token: str) -> str:
    logger.info("Verifying reset token.")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=400, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

async def validate_password_strength(password: str) -> None:
    logger.info("Validating password strength.")

    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one lowercase letter.")
    if not re.search(r"[0-9]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one number.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one special character.")

#==========OTP============
def verify_password_reset_otp(email: str, otp: str) -> bool:
    """Verify the 6-digit OTP sent to user's email"""
    logger.info(f"Verifying OTP for email: {email}")
    
    db = get_db()
    if db is None:
        logger.error("Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    user = db["users"].find_one({"email": email})
    
    if not user:
        logger.warning(f"No user found with email: {email}")
        logger.error("User not found")
        raise HTTPException(status_code=404, detail="User not found")
       
    if str(user.get("otp")) != otp:
        logger.warning(f"Invalid OTP for email: {email}")
        logger.error("Invalid OTP provided")
        raise HTTPException(status_code=400, detail="Invalid OTP")
    otp_created_at = user.get("otp_created_at")
    # Check if OTP is expired (e.g., older than 5 minutes)
    if isinstance(otp_created_at, str):
        otp_created_at = parser.isoparse(otp_created_at)
    elif otp_created_at and otp_created_at.tzinfo is None:
        otp_created_at = otp_created_at.replace(tzinfo=timezone.utc)

    # Now safe to compare
    if otp_created_at and (datetime.now(timezone.utc) - otp_created_at).total_seconds() > 300:
        logger.warning(f"OTP expired for email: {email}")
        raise HTTPException(status_code=400, detail="OTP expired")
    
    logger.info(f"OTP verified successfully for email: {email}")
    return True
def generate_otp(email: str) -> str:
    """Generate a 6-digit OTP for password reset"""
    logger.info(f"Generating OTP for email: {email}")
    generated_otp = randint(100000, 999999)
    # otp = OTP()
    
    # otp.otp = str(rand)
    # otp.created_at = datetime.now(timezone.utc)
    
    
    
    # Store OTP in the database
    logger.info(f"Storing OTP for email: {email}")
    db = get_db()
    if db is None:
        logger.error("Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    db["users"].update_one(
        {"email": email},
        {"$set": {"otp": generated_otp, "otp_created_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    
    return generated_otp

async def send_password_reset_otp(email: str) -> bool:
    """Send OTP to user's email for password reset"""
    logger.info(f"Sending OTP to email: {email}, Configuring FastMail to send OTP to {email}, from {EMAIL_FROM}, with {EMAIL_USERNAME}")
    
    otp = generate_otp(email)
    
    # Configure FastMail for sending emails
   
    message = MessageSchema(
        subject="Password Reset OTP",
        recipients=[email],
        body=f"Your OTP for password reset is: {otp}",
        subtype=MessageType.plain
    )
    
    print("\n\n\n\n, ", email, " type:", type(email))
    
    try:
        
        print("\n\n CONFIG: ", conf)
        fm = FastMail(conf)
        await fm.send_message(message)
        logger.info(f"OTP sent to {email}: {otp}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP to {email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send OTP")
