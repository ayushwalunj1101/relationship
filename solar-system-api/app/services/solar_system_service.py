from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.person import Person
from app.models.snapshot import Snapshot
from app.models.solar_system import SolarSystem
from app.models.tag import Tag
from app.services.stats_service import compute_stats


async def get_solar_system_by_user(db: AsyncSession, user_id: UUID) -> SolarSystem:
    """Fetch solar system by user_id. Raises 404 if not found."""
    result = await db.execute(
        select(SolarSystem).where(SolarSystem.user_id == user_id)
    )
    ss = result.scalar_one_or_none()
    if not ss:
        raise HTTPException(status_code=404, detail="Solar system not found for this user")
    return ss


async def get_full_solar_system(db: AsyncSession, user_id: UUID) -> dict | None:
    """
    Returns the complete current state for the frontend.
    Includes only active people, merged tags, theme, stats, and last_activity.
    """
    result = await db.execute(
        select(SolarSystem)
        .options(
            selectinload(SolarSystem.user),
            selectinload(SolarSystem.people).selectinload(Person.tag),
            selectinload(SolarSystem.tags),
        )
        .join(SolarSystem.user)
        .where(SolarSystem.user_id == user_id)
    )
    solar_system = result.scalar_one_or_none()
    if not solar_system:
        return None

    # Filter to active people only (removed_at IS NULL)
    active_people = [p for p in solar_system.people if p.removed_at is None]

    # Fetch predefined tags (solar_system_id IS NULL, is_predefined = True)
    predefined_result = await db.execute(
        select(Tag).where(Tag.is_predefined == True)  # noqa: E712
    )
    predefined_tags = predefined_result.scalars().all()

    # Merge predefined + custom tags (custom tags are in solar_system.tags)
    custom_tags = [t for t in solar_system.tags if not t.is_predefined]
    all_tags = list(predefined_tags) + custom_tags

    # Compute stats
    stats = await compute_stats(db, solar_system.id)

    # Get last activity (most recent snapshot timestamp)
    last_snap_result = await db.execute(
        select(Snapshot.created_at)
        .where(Snapshot.solar_system_id == solar_system.id)
        .order_by(Snapshot.created_at.desc())
        .limit(1)
    )
    last_activity = last_snap_result.scalar_one_or_none()

    return {
        "id": solar_system.id,
        "user": solar_system.user,
        "people": active_people,
        "tags": all_tags,
        "created_at": solar_system.created_at,
        "updated_at": solar_system.updated_at,
        "theme": solar_system.theme or {},
        "stats": stats,
        "last_activity": last_activity,
    }
