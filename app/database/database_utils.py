"""MongoDB database connection and initialization."""
from motor.motor_asyncio import AsyncIOMotorClient
from app.config.config import settings
from app.database.database_init import init_database

client = AsyncIOMotorClient(settings.MONGO_URI)
db = client["ai-sdlc-codereview-api"]

async def get_database():
    """Get database connection."""
    return db

async def initialize_database():
    """Initialize database with schema validation if enabled."""
    await init_database()