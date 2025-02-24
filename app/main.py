"""Main FastAPI application."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from logging import getLogger

from aws_embedded_metrics.config import get_config
from app.api.v1 import classifications, code_reviews, standard_sets
from app.config.config import settings
from app.database.database_utils import get_database, initialize_database
from app.common.logging import configure_logging, get_logger

Confg = get_config()

configure_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for database connection."""
    try:
        # Initialize database schema only during startup
        await initialize_database()
        app.state.db = await get_database()
        
        logger.info(f"EMF Environment: {Confg.environment}")
        logger.info(f"EMF Agent Endpoint: {Confg.agent_endpoint}")
        logger.info(f"EMF Service Name: {Confg.service_name}")
        yield
    finally:
        if hasattr(app.state, 'db') and hasattr(app.state.db, 'client'):
            app.state.db.client.close()

app = FastAPI(
    title="Defra AI Code Review API",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(classifications.router, prefix="/api/v1", tags=["Classifications"])
app.include_router(code_reviews.router, prefix="/api/v1", tags=["Code Reviews"])
app.include_router(standard_sets.router, prefix="/api/v1", tags=["Standard Sets"])

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"} 