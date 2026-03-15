from fastapi import APIRouter

from app.__version__ import __version__

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness():
    return {"status": "ok", "version": __version__}


@router.get("/ready")
async def readiness():
    return {"status": "ok", "version": __version__}
