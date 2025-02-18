from fastapi import APIRouter

router = APIRouter(prefix="/health")

# Do not remove - used for health checks
@router.get("/")
async def health():
    return {"status": "ok"}
