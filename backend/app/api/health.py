from fastapi import APIRouter

from ..domain.models import HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthStatus)
async def live() -> HealthStatus:
    return HealthStatus(status="ok")


@router.get("/health/ready", response_model=HealthStatus)
async def ready() -> HealthStatus:
    return HealthStatus(status="ok")
