from logging import getLogger
from contextlib import asynccontextmanager
from fastapi import FastAPI
from aws_embedded_metrics.config import get_config
from app.health.router import router as health_router
from app.example.router import router as example_router

Confg = get_config()
logger = getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"EMF Environment: {Confg.environment}")
    logger.info(f"EMF Agent Endpoint: {Confg.agent_endpoint}")
    logger.info(f"EMF Service Name: {Confg.service_name}")
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(health_router)
app.include_router(example_router)
