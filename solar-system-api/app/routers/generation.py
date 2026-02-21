import asyncio
import os
import subprocess
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.snapshot import Snapshot
from app.schemas.generation import (
    ImageGenerationResponse,
    VideoGenerationRequest,
    VideoGenerationResponse,
)
from app.services.image_generator import generate_solar_system_image
from app.services.solar_system_service import get_full_solar_system, get_solar_system_by_user
from app.services.video_generator import generate_video

router = APIRouter(tags=["generation"])


def _build_state_dict(solar_system_data: dict) -> dict:
    """Convert the ORM-based solar system data into a plain dict for image generation."""
    user = solar_system_data["user"]
    people = solar_system_data["people"]

    # Build tags_summary
    tags_summary: dict[str, int] = {}
    people_list = []
    for p in people:
        tag_info = None
        tag_name = "Untagged"
        if p.tag:
            tag_info = {"name": p.tag.name, "color": p.tag.color, "icon": p.tag.icon}
            tag_name = p.tag.name

        tags_summary[tag_name] = tags_summary.get(tag_name, 0) + 1
        people_list.append(
            {
                "id": str(p.id),
                "name": p.name,
                "x_position": p.x_position,
                "y_position": p.y_position,
                "distance_from_center": p.distance_from_center,
                "tag": tag_info,
                "avatar_url": p.avatar_url,
                "is_active": True,
                "orbit_speed": p.orbit_speed,
                "planet_size": p.planet_size,
                "custom_color": p.custom_color,
                "notes": p.notes,
                "relationship_score": p.relationship_score,
            }
        )

    return {
        "user": {
            "id": str(user.id),
            "name": user.name,
            "avatar_url": user.avatar_url,
        },
        "people": people_list,
        "tags_summary": tags_summary,
        "total_active_people": len(people_list),
        "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post(
    "/api/solar-system/{user_id}/generate-image",
    response_model=ImageGenerationResponse,
)
async def generate_image(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """Generate a Strava-style shareable image from the current solar system state."""
    solar_system_data = await get_full_solar_system(db, user_id)
    if not solar_system_data:
        raise HTTPException(status_code=404, detail="Solar system not found")

    state_dict = _build_state_dict(solar_system_data)

    filename = f"{user_id}_{int(datetime.now().timestamp())}.png"
    output_path = os.path.join(settings.GENERATED_DIR, "images", filename)

    # Run CPU-bound image generation in thread pool
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, generate_solar_system_image, state_dict, output_path)

    return ImageGenerationResponse(
        image_url=f"/generated/images/{filename}",
        generated_at=datetime.now(timezone.utc),
    )


@router.post(
    "/api/solar-system/{user_id}/generate-video",
    response_model=VideoGenerationResponse,
)
async def generate_video_endpoint(
    user_id: UUID,
    request_data: VideoGenerationRequest = VideoGenerationRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Generate a timeline video from all snapshots with smooth transitions."""
    ss = await get_solar_system_by_user(db, user_id)

    # Check FFmpeg availability
    try:
        subprocess.run(
            ["ffmpeg", "-version"], check=True, capture_output=True, timeout=10
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        raise HTTPException(
            status_code=503, detail="FFmpeg is not installed or not available on PATH"
        )

    # Count snapshots
    count_result = await db.execute(
        select(func.count())
        .select_from(Snapshot)
        .where(Snapshot.solar_system_id == ss.id)
    )
    snapshot_count = count_result.scalar()

    if snapshot_count < 2:
        raise HTTPException(
            status_code=400,
            detail="Need at least 2 snapshots to generate a video",
        )

    filename = f"{user_id}_{int(datetime.now().timestamp())}.mp4"
    output_path = os.path.join(settings.GENERATED_DIR, "videos", filename)

    await generate_video(
        db,
        ss.id,
        output_path,
        fps=request_data.fps,
        hold_seconds=request_data.duration_per_snapshot,
        transition_frames=request_data.transition_frames,
    )

    return VideoGenerationResponse(
        video_url=f"/generated/videos/{filename}",
        generated_at=datetime.now(timezone.utc),
        snapshot_count=snapshot_count,
    )
