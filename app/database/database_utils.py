"""MongoDB database connection and initialization."""
from motor.motor_asyncio import AsyncIOMotorClient
from app.config.config import settings
from app.database.database_init import init_database
from app.common.ssl_context import get_mongodb_ssl_options
import os

# Base MongoDB connection options - same as database_init.py
connection_options = {
    "retryWrites": True,
    "readPreference": "primary"
}

# Add AWS auth mechanism only if not in local development
if os.getenv('ENABLE_SECURE_CONTEXT', '') == 'true':
    connection_options["authMechanism"] = "MONGODB-AWS"

# Configure SSL/TLS if enabled
ssl_options, _ = get_mongodb_ssl_options()
if ssl_options:
    connection_options.update(ssl_options)

# Initialize client with same options as database_init.py
client = AsyncIOMotorClient(settings.MONGO_URI, **connection_options)
db = client[settings.MONGO_DATABASE]

async def get_database():
    """Get database connection."""
    return db

async def initialize_database():
    """Initialize database with schema validation if enabled."""
    await init_database()