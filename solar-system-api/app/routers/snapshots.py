from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.snapshot import Snapshot
from app.schemas.snapshot import SnapshotDetail, SnapshotPaginatedResponse
from app.services.solar_system_service import get_solar_system_by_user

router = APIRouter(
    prefix="/api/solar-system/{user_id}/snapshots", tags=["snapshots"]
)


@router.get("/", response_model=SnapshotPaginatedResponse)
async def list_snapshots(
    user_id: UUID,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List snapshots for a solar system (paginated, without full_state)."""
    ss = await get_solar_system_by_user(db, user_id)

    # Count total snapshots
    count_result = await db.execute(
        select(func.count()).select_from(Snapshot).where(
            Snapshot.solar_system_id == ss.id
        )
    )
    total = count_result.scalar()

    # Fetch page
    offset = (page - 1) * per_page
    result = await db.execute(
        select(Snapshot)
        .where(Snapshot.solar_system_id == ss.id)
        .order_by(Snapshot.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    snapshots = result.scalars().all()

    return SnapshotPaginatedResponse(
        snapshots=[
            {
                "id": s.id,
                "change_type": s.change_type,
                "change_summary": s.change_summary,
                "created_at": s.created_at,
            }
            for s in snapshots
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{snapshot_id}", response_model=SnapshotDetail)
async def get_snapshot(
    user_id: UUID,
    snapshot_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single snapshot with full_state JSON."""
    ss = await get_solar_system_by_user(db, user_id)

    snapshot = await db.get(Snapshot, snapshot_id)
    if not snapshot or snapshot.solar_system_id != ss.id:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    return snapshot
