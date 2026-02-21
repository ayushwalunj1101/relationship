from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.database import get_db
from app.schemas.solar_system import SolarSystemResponse, SolarSystemStats, ThemeUpdate
from app.services.solar_system_service import get_full_solar_system, get_solar_system_by_user
from app.services.stats_service import compute_stats
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/api/solar-system", tags=["solar-system"])


@router.get("/{user_id}", response_model=SolarSystemResponse)
async def get_solar_system(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Get the full solar system state for a user.
    Returns active people, all tags, theme, stats, and last_activity.
    """
    result = await get_full_solar_system(db, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Solar system not found")
    return result


@router.patch("/{user_id}/theme")
async def update_theme(
    user_id: UUID,
    theme_data: ThemeUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update the solar system's visual theme configuration.
    The backend stores this as-is; the frontend controls the schema.
    """
    ss = await get_solar_system_by_user(db, user_id)
    ss.theme = theme_data.theme
    ss.updated_at = func.now()
    await db.flush()

    await ws_manager.broadcast_to_user(
        user_id, "theme_updated", {"theme": theme_data.theme}
    )

    return {"theme": ss.theme}


@router.get("/{user_id}/stats", response_model=SolarSystemStats)
async def get_stats(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get computed analytics for the solar system."""
    ss = await get_solar_system_by_user(db, user_id)
    stats = await compute_stats(db, ss.id)
    return stats
