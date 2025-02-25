"""Centralized MongoDB connection management.

This module provides functions for creating and managing MongoDB connections
with consistent configuration across the application and child processes.
"""
import os
from typing import Dict, Any, Tuple, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config.config import settings
from app.common.ssl_context import get_mongodb_ssl_options
from app.common.logging import get_logger

logger = get_logger(__name__)

def get_connection_options() -> Dict[str, Any]:
    """Get standardized MongoDB connection options.
    
    Returns:
        Dict containing all connection options for MongoDB.
    """
    # Base MongoDB connection options
    connection_options = {
        "retryWrites": True,
        "readPreference": "primary"
    }
    
    # Add AWS auth mechanism only if in AWS
    if os.getenv('ENABLE_SECURE_CONTEXT', '') == 'true':
        connection_options["authMechanism"] = "MONGODB-AWS"
    
    # Configure SSL/TLS if enabled
    ssl_options, _ = get_mongodb_ssl_options()
    if ssl_options:
        connection_options.update(ssl_options)
        
    return connection_options

def create_client(uri: Optional[str] = None) -> Tuple[AsyncIOMotorClient, AsyncIOMotorDatabase]:
    """Create a new MongoDB client and database.
    
    Args:
        uri: Optional MongoDB URI. If not provided, uses the one from settings.
        
    Returns:
        Tuple of (client, database)
    """
    connection_uri = uri or settings.MONGO_URI
    connection_options = get_connection_options()
    
    client = AsyncIOMotorClient(connection_uri, **connection_options)
    db = client[settings.MONGO_DATABASE]
    
    return client, db 