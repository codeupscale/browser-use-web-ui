from pymongo import MongoClient
from pymongo.database import Database
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException
import logging
from dotenv import load_dotenv
import os
from ..utils.env_loader import load_env_from_root

# Logger setup
logger = logging.getLogger("db_connection")

# Load environment variables from the root .env file
load_env_from_root()

# MongoDB connection settings
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "300"))
MONGO_URL = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
logger.info(f"THIS IS THE MONGO_URL: {MONGO_URL}")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME") or os.getenv("DB_NAME", "nextsqa_db")
logger.info(f"THIS IS THE MONGO_DB_NAME: {MONGO_DB_NAME}")

# Global client instances (for reuse)
_sync_client = None
_async_client = None

def get_db() -> Database:
    """
    Get a MongoDB database connection (synchronous).
    """
    global _sync_client
    try:
        logger.info(f"THIS IS THE MONGO_URL: {MONGO_URL}")
        if not MONGO_URL:
            logger.error("MongoDB connection string not configured")
            raise HTTPException(status_code=500, detail="Database not configured")
            
        if _sync_client is None:
            logger.info(f"Connecting to MongoDB: {MONGO_URL[:50]}...")
            _sync_client = MongoClient(MONGO_URL)
            
        logger.info(f"THIS IS THE MONGO_DB_NAME: {MONGO_DB_NAME}")
        db = _sync_client[MONGO_DB_NAME]
        logger.info("Database connection established.")
        return db
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Database connection error")

async def get_async_db():
    """
    Get a MongoDB database connection (asynchronous).
    """
    global _async_client
    try:
        if not MONGO_URL:
            logger.error("MongoDB connection string not configured")
            raise HTTPException(status_code=500, detail="Database not configured")
            
        if _async_client is None:
            logger.info(f"Connecting to MongoDB (async): {MONGO_URL[:50]}...")
            _async_client = AsyncIOMotorClient(MONGO_URL)
            
        db = [MONGO_DB_NAME]
        logger.info("Async database connection established.")
        return db
    except Exception as e:
        logger.error(f"Async database connection error: {e}")
        raise HTTPException(status_code=500, detail="Database connection error")

def close_db(db: Database = None):
    """
    Close the MongoDB database connection (synchronous).
    """
    global _sync_client
    try:
        if db and hasattr(db, 'client'):
            db.client.close()
        elif _sync_client:
            _sync_client.close()
            _sync_client = None
        logger.info("Database connection closed.")
    except Exception as e:
        logger.error(f"Error closing database connection: {e}")
        raise HTTPException(status_code=500, detail="Error closing database connection")

async def close_async_db():
    """
    Close the MongoDB database connection (asynchronous).
    """
    global _async_client
    try:
        if _async_client:
            _async_client.close()
            _async_client = None
        logger.info("Async database connection closed.")
    except Exception as e:
        logger.error(f"Error closing async database connection: {e}")

def check_db_health() -> dict:
    """
    Check database health and connectivity.
    Returns detailed health information.
    """
    health_info = {
        "healthy": False,
        "database": "unknown",
        "connection_string": "not_configured",
        "database_name": MONGO_DB_NAME,
        "error": None,
        "server_info": None,
        "collections_count": None
    }
    
    try:
        # Check if connection string is configured
        if not MONGO_URL:
            health_info.update({
                "error": "MongoDB connection string not configured",
                "connection_string": "missing"
            })
            logger.warning("MongoDB health check failed: No connection string")
            return health_info
            
        # Mask sensitive parts of connection string for logging
        masked_url = MONGO_URL[:50] + "..." if len(MONGO_URL) > 50 else MONGO_URL
        health_info["connection_string"] = "configured"
        
        # Test connection
        client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)  # 5 second timeout
        
        # Ping the database
        client.admin.command('ping')
        logger.info("MongoDB ping successful")
        
        # Get database
        db = client[MONGO_DB_NAME]
        
        # Get server info
        server_info = client.server_info()
        health_info["server_info"] = {
            "version": server_info.get("version"),
            "git_version": server_info.get("gitVersion"),
            "platform": server_info.get("platform")
        }
        
        # Count collections
        collections = db.list_collection_names()
        health_info["collections_count"] = len(collections)
        
        # Test a simple operation
        db.admin.command('serverStatus')
        
        health_info.update({
            "healthy": True,
            "database": "connected",
            "message": "Database is healthy and responsive"
        })
        
        logger.info(f"MongoDB health check passed. Collections: {len(collections)}")
        
        # Close the test connection
        client.close()
        
    except Exception as e:
        error_msg = str(e)
        health_info.update({
            "healthy": False,
            "database": "error",
            "error": error_msg
        })
        logger.error(f"MongoDB health check failed: {error_msg}")
    
    return health_info

async def check_async_db_health() -> dict:
    """
    Check database health asynchronously.
    """
    health_info = {
        "healthy": False,
        "database": "unknown",
        "connection_string": "not_configured",
        "database_name": MONGO_DB_NAME,
        "error": None,
        "server_info": None,
        "collections_count": None
    }
    
    try:
        if not MONGO_URL:
            health_info.update({
                "error": "MongoDB connection string not configured",
                "connection_string": "missing"
            })
            return health_info
            
        health_info["connection_string"] = "configured"
        
        # Test async connection
        client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        
        # Ping the database
        await client.admin.command('ping')
        logger.info("MongoDB async ping successful")
        
        # Get database
        db = client[MONGO_DB_NAME]
        
        # Get server info
        server_info = await client.admin.command('serverStatus')
        health_info["server_info"] = {
            "version": server_info.get("version"),
            "host": server_info.get("host"),
            "uptime": server_info.get("uptime")
        }
        
        # Count collections
        collections = await db.list_collection_names()
        health_info["collections_count"] = len(collections)
        
        health_info.update({
            "healthy": True,
            "database": "connected",
            "message": "Async database is healthy and responsive"
        })
        
        logger.info(f"MongoDB async health check passed. Collections: {len(collections)}")
        
        # Close the test connection
        client.close()
        
    except Exception as e:
        error_msg = str(e)
        health_info.update({
            "healthy": False,
            "database": "error",
            "error": error_msg
        })
        logger.error(f"MongoDB async health check failed: {error_msg}")
    
    return health_info

# Utility functions for connection info
def get_connection_info() -> dict:
    """Get MongoDB connection information (without sensitive data)"""
    return {
        "database_name": MONGO_DB_NAME,
        "connection_configured": bool(MONGO_URL),
        "connection_type": "MongoDB Atlas" if "mongodb.net" in (MONGO_URL or "") else "MongoDB",
    }

def test_database_operation() -> bool:
    """Test a basic database operation"""
    try:
        db = get_db()
        # Test inserting and removing a test document
        test_collection = db.test_health_check
        result = test_collection.insert_one({"test": "health_check", "timestamp": "now"})
        test_collection.delete_one({"_id": result.inserted_id})
        logger.info("Database operation test successful")
        return True
    except Exception as e:
        logger.error(f"Database operation test failed: {e}")
        return False