from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.solar_system import SolarSystemResponse
from app.services.solar_system_service import get_full_solar_system

router = APIRouter(prefix="/api/solar-system", tags=["solar-system"])


@router.get("/{user_id}", response_model=SolarSystemResponse)
async def get_solar_system(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Get the full solar system state for a user.
    Returns only active people (removed_at IS NULL) and all tags (predefined + custom).
    """
    result = await get_full_solar_system(db, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Solar system not found")
    return result
