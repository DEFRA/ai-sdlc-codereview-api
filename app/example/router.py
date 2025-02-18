from os import environ
from logging import getLogger
from fastapi import APIRouter
from app.common.metrics import counter

router = APIRouter(prefix="/example")

logger = getLogger(__name__)

# remove this example route
@router.get("/")
async def root():
    region = environ.get("AWS_REGION")

    logger.info(f"Region: {region}")

    counter("Root", 1)

    return {"region": region}
