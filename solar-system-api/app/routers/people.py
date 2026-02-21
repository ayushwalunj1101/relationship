import math
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.database import get_db
from app.models.person import Person
from app.schemas.person import BulkPositionUpdate, PersonCreate, PersonResponse, PersonUpdate
from app.services.snapshot_service import capture_snapshot
from app.services.solar_system_service import get_solar_system_by_user
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/api/solar-system/{user_id}/people", tags=["people"])


@router.post("/", response_model=PersonResponse, status_code=201)
async def add_person(
    user_id: UUID,
    person_data: PersonCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a person to the solar system. Creates a snapshot."""
    ss = await get_solar_system_by_user(db, user_id)

    # Compute distance from center
    distance = math.sqrt(person_data.x_position**2 + person_data.y_position**2)

    # Create person
    person = Person(
        solar_system_id=ss.id,
        name=person_data.name,
        x_position=person_data.x_position,
        y_position=person_data.y_position,
        distance_from_center=distance,
        tag_id=person_data.tag_id,
        avatar_url=person_data.avatar_url,
        orbit_speed=person_data.orbit_speed,
        planet_size=person_data.planet_size,
        custom_color=person_data.custom_color,
        notes=person_data.notes,
        relationship_score=person_data.relationship_score,
    )
    db.add(person)
    await db.flush()
    await db.refresh(person, attribute_names=["tag"])

    # Determine tag name for summary
    tag_name = person.tag.name if person.tag else "Untagged"

    # Update solar system updated_at
    ss.updated_at = func.now()
    await db.flush()

    # Create snapshot
    await capture_snapshot(
        db, ss.id, "person_added", f"Added {person.name} as {tag_name}"
    )

    await ws_manager.broadcast_to_user(
        user_id, "person_added", {"person_id": str(person.id), "name": person.name}
    )

    return person


@router.patch("/bulk", response_model=list[PersonResponse])
async def bulk_update_positions(
    user_id: UUID,
    bulk_data: BulkPositionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Bulk update positions for multiple people at once.
    Creates a single snapshot with change_type='bulk_update'.
    """
    ss = await get_solar_system_by_user(db, user_id)

    if not bulk_data.updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    person_ids = [item.person_id for item in bulk_data.updates]

    # Fetch all people in one query
    result = await db.execute(
        select(Person).where(
            Person.id.in_(person_ids),
            Person.solar_system_id == ss.id,
            Person.removed_at.is_(None),
        )
    )
    people_map = {p.id: p for p in result.scalars().all()}

    # Validate all exist
    for item in bulk_data.updates:
        if item.person_id not in people_map:
            raise HTTPException(
                status_code=404,
                detail=f"Person {item.person_id} not found or not active",
            )

    # Apply all updates
    updated_people = []
    for item in bulk_data.updates:
        person = people_map[item.person_id]
        person.x_position = item.x_position
        person.y_position = item.y_position
        person.distance_from_center = math.sqrt(
            item.x_position**2 + item.y_position**2
        )
        updated_people.append(person)

    await db.flush()

    for person in updated_people:
        await db.refresh(person, attribute_names=["tag"])

    ss.updated_at = func.now()
    await db.flush()

    count = len(updated_people)
    await capture_snapshot(
        db, ss.id, "bulk_update", f"Bulk updated {count} people's positions"
    )

    await ws_manager.broadcast_to_user(
        user_id,
        "bulk_update",
        {
            "updated_count": count,
            "people": [
                {
                    "id": str(p.id),
                    "x_position": p.x_position,
                    "y_position": p.y_position,
                    "distance_from_center": p.distance_from_center,
                }
                for p in updated_people
            ],
        },
    )

    return updated_people


@router.patch("/{person_id}", response_model=PersonResponse)
async def update_person(
    user_id: UUID,
    person_id: UUID,
    update_data: PersonUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a person's position, tag, or other fields. Creates a snapshot."""
    ss = await get_solar_system_by_user(db, user_id)

    person = await db.get(Person, person_id)
    if not person or person.solar_system_id != ss.id:
        raise HTTPException(status_code=404, detail="Person not found")
    if person.removed_at is not None:
        raise HTTPException(status_code=410, detail="Person has been removed")

    old_distance = person.distance_from_center
    position_changed = False
    tag_changed = False

    # Apply updates
    if update_data.name is not None:
        person.name = update_data.name

    if update_data.avatar_url is not None:
        person.avatar_url = update_data.avatar_url

    if update_data.x_position is not None or update_data.y_position is not None:
        if update_data.x_position is not None:
            person.x_position = update_data.x_position
        if update_data.y_position is not None:
            person.y_position = update_data.y_position
        person.distance_from_center = math.sqrt(
            person.x_position**2 + person.y_position**2
        )
        position_changed = True

    if update_data.tag_id is not None:
        person.tag_id = update_data.tag_id
        tag_changed = True

    # Apply new animation/visualization fields
    if update_data.orbit_speed is not None:
        person.orbit_speed = update_data.orbit_speed
    if update_data.planet_size is not None:
        person.planet_size = update_data.planet_size
    if update_data.custom_color is not None:
        person.custom_color = update_data.custom_color
    if update_data.notes is not None:
        person.notes = update_data.notes
    if update_data.relationship_score is not None:
        person.relationship_score = update_data.relationship_score

    await db.flush()
    await db.refresh(person, attribute_names=["tag"])

    # Update solar system updated_at
    ss.updated_at = func.now()
    await db.flush()

    # Determine change type and summary
    if position_changed:
        direction = "closer" if person.distance_from_center < old_distance else "further"
        change_type = "person_moved"
        change_summary = f"Moved {person.name} {direction}"
    elif tag_changed:
        tag_name = person.tag.name if person.tag else "Untagged"
        change_type = "person_tag_changed"
        change_summary = f"Changed {person.name}'s tag to {tag_name}"
    else:
        change_type = "person_moved"
        change_summary = f"Updated {person.name}"

    # Create snapshot
    await capture_snapshot(db, ss.id, change_type, change_summary)

    await ws_manager.broadcast_to_user(
        user_id, change_type, {"person_id": str(person.id), "name": person.name}
    )

    return person


@router.delete("/{person_id}")
async def remove_person(
    user_id: UUID,
    person_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a person. Creates a snapshot."""
    ss = await get_solar_system_by_user(db, user_id)

    person = await db.get(Person, person_id)
    if not person or person.solar_system_id != ss.id:
        raise HTTPException(status_code=404, detail="Person not found")
    if person.removed_at is not None:
        raise HTTPException(status_code=410, detail="Person already removed")

    person_name = person.name
    person.removed_at = datetime.now(timezone.utc)
    await db.flush()

    # Update solar system updated_at
    ss.updated_at = func.now()
    await db.flush()

    # Create snapshot
    await capture_snapshot(db, ss.id, "person_removed", f"Removed {person_name}")

    await ws_manager.broadcast_to_user(
        user_id, "person_removed", {"person_id": str(person_id), "name": person_name}
    )

    return {"message": "Person removed", "id": str(person_id)}
