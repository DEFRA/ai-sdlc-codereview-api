"""Database initialization module."""
import os
from datetime import datetime, UTC
from app.config.config import settings
from app.models.code_review import ReviewStatus
from app.common.ssl_context import get_mongodb_ssl_options
from app.common.logging import get_logger
from app.database.connection import create_client

logger = get_logger(__name__)

# MongoDB validation schemas
classifications_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name"],
        "properties": {
            "_id": {
                "bsonType": "objectId",
                "description": "Unique identifier"
            },
            "name": {
                "bsonType": "string",
                "description": "Classification name"
            }
        }
    }
}

standard_sets_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "repository_url"],
        "properties": {
            "_id": {
                "bsonType": "objectId",
                "description": "Unique identifier"
            },
            "name": {
                "bsonType": "string",
                "description": "Standard set name"
            },
            "repository_url": {
                "bsonType": "string",
                "description": "URL of the repository containing standards"
            },
            "custom_prompt": {
                "bsonType": "string",
                "description": "Custom prompt for LLM processing"
            },
            "created_at": {
                "bsonType": "date",
                "description": "Creation timestamp"
            },
            "updated_at": {
                "bsonType": "date",
                "description": "Last update timestamp"
            }
        }
    }
}

standards_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["text", "repository_path", "standard_set_id", "classification_ids", "created_at", "updated_at"],
        "properties": {
            "_id": {
                "bsonType": "objectId",
                "description": "Unique identifier"
            },
            "text": {
                "bsonType": "string",
                "description": "Standard text content"
            },
            "repository_path": {
                "bsonType": "string",
                "description": "Path to the standard in the repository"
            },
            "standard_set_id": {
                "bsonType": "objectId",
                "description": "Reference to the standard set"
            },
            "classification_ids": {
                "bsonType": "array",
                "items": {
                    "bsonType": "objectId",
                    "description": "Reference to classifications"
                },
                "description": "List of classification references"
            },
            "created_at": {
                "bsonType": "date",
                "description": "Creation timestamp"
            },
            "updated_at": {
                "bsonType": "date",
                "description": "Last update timestamp"
            }
        }
    }
}

code_review_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["repository_url", "status", "standard_sets", "created_at", "updated_at"],
        "properties": {
            "_id": {
                "bsonType": "objectId",
                "description": "Unique identifier"
            },
            "repository_url": {
                "bsonType": "string",
                "description": "Repository URL to analyze"
            },
            "status": {
                "enum": [s.value for s in ReviewStatus],
                "description": "Current review status"
            },
            "standard_sets": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["_id", "name"],
                    "properties": {
                        "_id": {
                            "bsonType": "objectId",
                            "description": "Standard set identifier"
                        },
                        "name": {
                            "bsonType": "string",
                            "description": "Name of the standard set"
                        }
                    }
                }
            },
            "compliance_reports": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["_id", "standard_set_name", "file", "report"],
                    "properties": {
                        "_id": {
                            "bsonType": "objectId",
                            "description": "Report identifier"
                        },
                        "standard_set_name": {
                            "bsonType": "string",
                            "description": "Name of the standard set"
                        },
                        "file": {
                            "bsonType": "string",
                            "description": "File path being reviewed"
                        },
                        "report": {
                            "bsonType": "string",
                            "description": "Detailed compliance report"
                        }
                    }
                }
            },
            "created_at": {
                "bsonType": "date",
                "description": "Creation timestamp"
            },
            "updated_at": {
                "bsonType": "date",
                "description": "Last update timestamp"
            }
        }
    }
}

async def init_database():
    """Initialize database with schema validation.
    
    Sets up MongoDB connection with proper SSL/TLS configuration and 
    initializes collections with schema validation.
    
    Returns:
        AsyncIOMotorDatabase: Initialized database instance
    """
    # Configure SSL/TLS if enabled
    _, temp_ca_file = get_mongodb_ssl_options()
    
    try:
        # Initialize MongoDB client and test connection
        client, db = create_client()
        await client.admin.command('ping')
        
        # Create collections with schema validation
        collections_config = {
            "code_reviews": code_review_schema,
            "classifications": classifications_schema,
            "standard_sets": standard_sets_schema,
            "standards": standards_schema
        }

        try:
            for collection_name, schema in collections_config.items():
                if collection_name not in await db.list_collection_names():
                    try:
                        await db.create_collection(
                            collection_name,
                            validator=schema
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to create collection {collection_name} with schema validation. "
                            f"Creating without validation. Error: {str(e)}"
                        )
                        await db.create_collection(collection_name)
                else:
                    try:
                        await db.command({
                            "collMod": collection_name,
                            "validator": schema
                        })
                    except Exception as e:
                        logger.warning(
                            f"Failed to update schema validation for {collection_name}. "
                            f"Continuing without validation. Error: {str(e)}"
                        )
        except Exception as e:
            logger.warning(
                "Failed to set up schema validation. "
                "Application will continue without schema validation. "
                f"Error: {str(e)}"
            )
                
        return db
        
    finally:
        # Clean up temporary certificate file
        if temp_ca_file:
            try:
                os.unlink(temp_ca_file)
            except Exception as e:
                logger.error(
                    "Failed to remove temporary CA file",
                    extra={"error": str(e)}
                )
