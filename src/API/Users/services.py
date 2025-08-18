from passlib.context import CryptContext
from typing import Optional
from fastapi import HTTPException, status
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
import logging
import os
from .models import UserModel 
from .schemas import UserCreate
from dotenv import load_dotenv
from ..db.db_connection import get_db, close_db
from ..core.security import validate_password_strength, verify_reset_token, send_password_reset_otp, verify_password_reset_otp
from ..utils.env_loader import load_env_from_root

# Load environment variables from the root .env file
load_env_from_root()

# Configuration constants loaded from environment variables
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")  # Default to HS256 if not specified
RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "300"))  # Default 5 hours

# Logger setup for tracking user service operations
logger = logging.getLogger("user_service")
logging.basicConfig(level=logging.INFO)

# Password hashing context using bcrypt algorithm
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Secret key for reset tokens (you should store this securely


def login_user(email: str, password: str) -> Optional[dict]:
    # Authenticate user login and generate JWT access token
    # Args: email (str): User's email address, password (str): Plain text password
    # Returns: Optional[dict]: Dictionary containing access token info or None if authentication fails
    logger.info(f"Authenticating user with email: {email}")

    # Establish database connection
    db = get_db()
    if db is None:
        logger.error("Database connection failed.")
        raise HTTPException(status_code=500, detail="Database connection error")

    # Search for user in database by email
    logger.info(f"Searching for user in database with email: {email}")
    print("\n\n EMAIL:" , email)
        
    try:
        user = db["users"].find_one({"email": email})
        print("\n SUCCESS: ", user)
    except Exception as e:
        print("\n\n FOLLOWING ERRRE OCCURED:", e)

    # Verify user exists and password is correct
    if not user or not verify_password(password, user["hashed_password"]):
        logger.warning(f"Authentication failed for email: {email}")
        return None

    # Generate JWT token with expiration time
    logger.info(f"Authentication successful for {email}, generating JWT token")
    expire = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user["email"], "exp": expire}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    logger.info(f"JWT token generated successfully for {email}")
    return {"access_token": token, "token_type": "bearer", "email": user["email"]}


def hash_password(password: str) -> str:
    # Hash a plain text password using bcrypt
    # Args: password (str): Plain text password to hash
    # Returns: str: Hashed password
    logger.info("Hashing password.")
    hashed_pw = pwd_context.hash(password)
    logger.info("Password hashed successfully")
    return hashed_pw


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Verify a plain text password against a hashed password
    # Args: plain_password (str): Plain text password to verify, hashed_password (str): Stored hashed password
    # Returns: bool: True if password matches, False otherwise
    logger.info("Verifying password.")
    is_valid = pwd_context.verify(plain_password, hashed_password)
    logger.info(f"Password verification result: {is_valid}")
    return is_valid


async def create_user(user: UserCreate) -> UserModel:
    # Create a new user account in the system
    # Args: user (UserCreate): User creation data schema
    # Returns: UserModel: Created user model or raises HTTPException
    logger.info(f"Creating user with email: {user.email}")
    
    # Establish database connection
    db = get_db()
    print(f"Database connection: {db}")
    if db is None:
        logger.error("Database connection failed.")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    # Check if user already exists with this email
    logger.info(f"Checking if user already exists with email: {user.email}")
    existing = db["users"].find_one({"email": user.email})
    
    if existing:
        logger.warning(f"Email already registered: {user.email}")
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate password strength before proceeding
    logger.info(f"Validating password strength for user: {user.email}")
    validate_password_strength(user.password)
    logger.info("Password strength validation passed")
    
    # Hash the password for secure storage
    logger.info("Hashing user password")
    hashed_pw = hash_password(user.password)
    
    # Create new user model instance
    logger.info(f"Creating UserModel instance for {user.email}")
    new_user = UserModel(
        firstname=user.firstname,
        lastname=user.lastname,
        email=user.email,
        hashed_password=hashed_pw,
        organization=user.organization,
        role=user.role,
        status=user.status,
    )
    
    # Insert the user dictionary into MongoDB
    logger.info(f"Inserting new user into database: {user.email}")
    db["users"].insert_one(new_user.dict())
    logger.info(f"User created successfully: {user.email}")
    return True


def generate_reset_token(email: str) -> str:
    # Generate a JWT token for password reset functionality
    # Args: email (str): User's email address
    # Returns: str: JWT reset token
    logger.info(f"Generating reset token for: {email}")
    
    # Set token expiration time
    expire = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    logger.info(f"Reset token will expire at: {expire}")
    
    # Create JWT payload with email and expiration
    payload = {"sub": email, "exp": expire}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    logger.info(f"Reset token generated successfully for: {email}")
    return token


def find_user_by_email(email: str) -> Optional[dict]:
    # Find user by email in MongoDB users collection
    # Args: email (str): User's email address
    # Returns: Optional[dict]: User document or None if not found
    logger.info(f"Searching for user by email: {email}")
    
    # Establish database connection
    db = get_db()
    if db is None:
        logger.error("Database connection failed")
        return None
    
    # Search for user in database
    user = db["users"].find_one({"email": email})
    
    if user:
        logger.info(f"User found with email: {email}")
    else:
        logger.warning(f"No user found with email: {email}")
    
    return user


async def reset_user_password(token: str, new_password1: str, new_password2: str) -> bool:
    # Reset user password using a JWT reset token
    # Args: token (str): JWT reset token, new_password1 (str): New password, new_password2 (str): New password confirmation
    # Returns: bool: True if password reset successful, raises HTTPException otherwise
    logger.info(f"Resetting password using token: {token}")
    
    # Verify the reset token and extract email
    logger.info("Verifying reset token")
    email = verify_reset_token(token)
    if not email:
        logger.error("Invalid or expired token")
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    
    logger.info(f"Reset token verified successfully for email: {email}")
    
    # Validate new password strength
    logger.info("Validating new password strength")
    validate_password_strength(new_password1)
    
    # Ensure both password fields match
    if new_password1 != new_password2:
        logger.error("New passwords do not match")
        raise HTTPException(status_code=400, detail="New passwords do not match")
    
    logger.info("New passwords match, proceeding with reset")

    # Hash the new password
    logger.info("Hashing new password")
    hashed_password = hash_password(new_password1)
    
    # Establish database connection
    db = get_db()
    if db is None:
        logger.error("Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    # Update the user's password in the database
    logger.info(f"Updating password in database for email: {email}")
    result = db["users"].update_one(
        {"email": email},
        {"$set": {"hashed_password": hashed_password}}
    )
    
    # Check if update was successful
    if result.modified_count == 0:
        logger.error(f"Failed to reset password for {email}")
        return False
    
    logger.info(f"Password reset successful for {email}")
    return True

 
async def forgot_password_otp(email: str) -> bool:
    # Send password reset OTP to user's email
    # Args: email (str): User's email address
    # Returns: bool: True if OTP sent successfully, False if user not found
    logger.info(f"Sending password reset OTP to: {email}")
    
    # Establish database connection
    db = get_db()
    if db is None:
        logger.error("Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    # Verify user exists in database
    logger.info(f"Verifying user exists with email: {email}")
    user = db["users"].find_one({"email": email})
    
    if not user:
        logger.warning(f"No user found with email: {email}")
        return False
    
    logger.info(f"User found, generating OTP for: {email}")
    
    # Generate and send OTP via security module
    otp = await send_password_reset_otp(email)
    
    # Here you would send the OTP via email (not implemented in this example)
    # send_email(user.email, "Your OTP", f"Your OTP is: {otp}")
    
    logger.info(f"OTP sent to {email}: {otp}")
    return True


async def update_password_with_otp(email: str, otp: str, new_password1: str, new_password2: str) -> bool:
    # Reset password using OTP verification
    # Args: email (str): User's email address, otp (str): One-time password received by user
    # new_password1 (str): New password, new_password2 (str): New password confirmation
    # Returns: bool: True if password updated successfully, raises HTTPException otherwise
    logger.info(f"Updating password for {email} using OTP")
    
    # Establish database connection
    db = get_db()
    if db is None:
        logger.error("Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection error")
    
    # Verify user exists in database
    logger.info(f"Verifying user exists with email: {email}")
    user = db["users"].find_one({"email": email})
    
    if not user:
        logger.warning(f"No user found with email: {email}")
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify the OTP is valid
    logger.info(f"Verifying OTP for email: {email}")
    verify_password_reset_otp(email, otp)
    logger.info("OTP verification successful")
    
    # Validate new password strength
    logger.info("Validating new password strength")
    await validate_password_strength(new_password1)
    
    # Ensure both password fields match
    if new_password1 != new_password2:
        logger.error("New passwords do not match")
        raise HTTPException(status_code=400, detail="New passwords do not match")
    
    logger.info("New passwords match, proceeding with update")
    
    # Hash the new password
    logger.info("Hashing new password")
    hashed_password = hash_password(new_password1)
    logger.info(f"New password hashed for {email}")
    
    # Update the user's password in the database and clear OTP
    logger.info(f"Updating password in database for email: {email}")
    result = db["users"].update_one(
        {"email": email},
        {"$set": {"hashed_password": hashed_password, "otp": None}}  # Clear OTP after use
    )
    
    # Check if update was successful
    if result.modified_count == 0:
        logger.error(f"Failed to update password for {email}")
        return False
    
    logger.info(f"Password updated successfully for {email}")
    return True