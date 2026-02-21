from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.person import Person
from app.models.snapshot import Snapshot
from app.models.solar_system import SolarSystem


async def capture_snapshot(
    db: AsyncSession,
    solar_system_id: UUID,
    change_type: str,
    change_summary: str,
) -> Snapshot:
    """
    Captures the FULL current state of the solar system and saves it as a snapshot.
    Called after every mutation (add/move/remove person, etc.)

    Must be called AFTER the mutation has been flushed but BEFORE commit.
    """
    # Fetch solar system with user and all people (with their tags)
    result = await db.execute(
        select(SolarSystem)
        .options(
            selectinload(SolarSystem.user),
            selectinload(SolarSystem.people).selectinload(Person.tag),
        )
        .where(SolarSystem.id == solar_system_id)
    )
    ss = result.scalar_one()

    # Filter to active people only (removed_at IS NULL)
    active_people = [p for p in ss.people if p.removed_at is None]

    # Build tags_summary count
    tags_summary: dict[str, int] = {}
    for person in active_people:
        tag_name = person.tag.name if person.tag else "Untagged"
        tags_summary[tag_name] = tags_summary.get(tag_name, 0) + 1

    # Build full_state JSON
    full_state = {
        "user": {
            "id": str(ss.user.id),
            "name": ss.user.name,
            "avatar_url": ss.user.avatar_url,
        },
        "people": [
            {
                "id": str(p.id),
                "name": p.name,
                "x_position": p.x_position,
                "y_position": p.y_position,
                "distance_from_center": p.distance_from_center,
                "tag": {
                    "name": p.tag.name,
                    "color": p.tag.color,
                    "icon": p.tag.icon,
                }
                if p.tag
                else None,
                "avatar_url": p.avatar_url,
                "is_active": True,
                "orbit_speed": p.orbit_speed,
                "planet_size": p.planet_size,
                "custom_color": p.custom_color,
                "notes": p.notes,
                "relationship_score": p.relationship_score,
            }
            for p in active_people
        ],
        "tags_summary": tags_summary,
        "total_active_people": len(active_people),
        "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Create and save the snapshot
    snapshot = Snapshot(
        solar_system_id=solar_system_id,
        full_state=full_state,
        change_type=change_type,
        change_summary=change_summary,
    )
    db.add(snapshot)
    await db.flush()

    return snapshot
