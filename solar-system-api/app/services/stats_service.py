from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.person import Person
from app.models.snapshot import Snapshot
from app.models.tag import Tag


async def compute_stats(db: AsyncSession, solar_system_id: UUID) -> dict:
    """Compute analytics for a solar system."""
    result = await db.execute(
        select(Person).where(
            Person.solar_system_id == solar_system_id,
            Person.removed_at.is_(None),
        )
    )
    active_people = result.scalars().all()

    total_people = len(active_people)

    if total_people == 0:
        return {
            "total_people": 0,
            "average_distance": 0.0,
            "closest_person": None,
            "furthest_person": None,
            "tag_distribution": {},
            "relationship_score_distribution": _empty_score_distribution(),
            "timeline_activity": await _get_timeline_activity(db, solar_system_id),
        }

    distances = [(p.name, p.distance_from_center) for p in active_people]
    avg_distance = round(sum(d for _, d in distances) / total_people, 4)

    closest = min(distances, key=lambda x: x[1])
    furthest = max(distances, key=lambda x: x[1])

    # Tag distribution
    tag_ids = {p.tag_id for p in active_people if p.tag_id is not None}
    tag_name_map: dict = {}
    if tag_ids:
        tag_result = await db.execute(
            select(Tag.id, Tag.name).where(Tag.id.in_(tag_ids))
        )
        tag_name_map = {row.id: row.name for row in tag_result}

    tag_distribution: dict[str, int] = {}
    for p in active_people:
        tag_name = tag_name_map.get(p.tag_id, "Untagged") if p.tag_id else "Untagged"
        tag_distribution[tag_name] = tag_distribution.get(tag_name, 0) + 1

    return {
        "total_people": total_people,
        "average_distance": avg_distance,
        "closest_person": {"name": closest[0], "distance": round(closest[1], 4)},
        "furthest_person": {"name": furthest[0], "distance": round(furthest[1], 4)},
        "tag_distribution": tag_distribution,
        "relationship_score_distribution": _compute_score_distribution(active_people),
        "timeline_activity": await _get_timeline_activity(db, solar_system_id),
    }


def _empty_score_distribution() -> dict[str, int]:
    return {"0-25": 0, "26-50": 0, "51-75": 0, "76-100": 0, "unscored": 0}


def _compute_score_distribution(people: list) -> dict[str, int]:
    dist = _empty_score_distribution()
    for p in people:
        score = p.relationship_score
        if score is None:
            dist["unscored"] += 1
        elif score <= 25:
            dist["0-25"] += 1
        elif score <= 50:
            dist["26-50"] += 1
        elif score <= 75:
            dist["51-75"] += 1
        else:
            dist["76-100"] += 1
    return dist


async def _get_timeline_activity(
    db: AsyncSession, solar_system_id: UUID
) -> list[dict]:
    """Get change counts per day for the last 30 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    result = await db.execute(
        select(
            cast(Snapshot.created_at, Date).label("date"),
            func.count().label("change_count"),
        )
        .where(
            Snapshot.solar_system_id == solar_system_id,
            Snapshot.created_at >= cutoff,
        )
        .group_by(cast(Snapshot.created_at, Date))
        .order_by(cast(Snapshot.created_at, Date))
    )
    rows = result.all()

    return [
        {"date": row.date.isoformat(), "change_count": row.change_count}
        for row in rows
    ]
