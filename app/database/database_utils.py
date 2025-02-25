"""MongoDB database connection and initialization."""
from app.database.database_init import init_database
from app.database.connection import create_client

# Initialize client with centralized connection options
client, db = create_client()

async def get_database():
    """Get database connection."""
    return db

async def initialize_database():
    """Initialize database with schema validation if enabled."""
    await init_database()