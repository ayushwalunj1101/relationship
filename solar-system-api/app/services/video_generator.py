"""
Timeline video generator for the Relationship Solar System.

Renders individual frames using the same visual style as the image generator,
then stitches them into an MP4 using FFmpeg.
"""

import asyncio
import logging
import os
import tempfile
from uuid import UUID

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.snapshot import Snapshot
from app.services.image_generator import (
    CENTER,
    HEIGHT,
    SCALE,
    WIDTH,
    _draw_connections,
    _draw_orbital_rings,
    _draw_radial_gradient,
    _draw_stars,
    _draw_title,
    _get_fonts,
    _draw_people_glow,
    _draw_people_solid,
    _draw_center_user,
    _draw_stats_bar,
)
from app.utils.interpolation import interpolate_snapshots

logger = logging.getLogger(__name__)

# Default video parameters
DEFAULT_FPS = 30
DEFAULT_HOLD_FRAMES = 60  # 2 seconds at 30fps
DEFAULT_TRANSITION_FRAMES = 15  # 0.5 seconds


def _render_frame(
    state: dict,
    frame_number: int,
    total_frames: int,
    change_summary: str | None = None,
) -> Image.Image:
    """
    Render a single video frame.

    Same visual style as the image generator, with additions:
    - Per-person alpha support (for fade in/out during transitions)
    - Change summary text overlay
    - Timeline progress bar
    """
    fonts = _get_fonts()

    # Base image
    img = Image.new("RGBA", (WIDTH, HEIGHT), (10, 10, 26, 255))

    # Background gradient
    img = _draw_radial_gradient(img)

    draw = ImageDraw.Draw(img)

    # Star field
    seed = state.get("user", {}).get("id", "default")
    _draw_stars(draw, seed)

    # Orbital rings
    _draw_orbital_rings(draw)

    people = state.get("people", [])

    # Connection lines
    _draw_connections(draw, people)

    # People glow (handles per-person alpha)
    img = _draw_people_glow(img, people)

    # People solid circles + labels (handles per-person alpha)
    draw = ImageDraw.Draw(img)
    _draw_people_solid(draw, people, fonts)

    # Center user
    img = _draw_center_user(img, state.get("user", {}), fonts)

    # Stats bar
    img = _draw_stats_bar(img, state, fonts)

    # Title
    draw = ImageDraw.Draw(img)
    _draw_title(draw, fonts)

    # Change summary overlay (above stats bar)
    if change_summary:
        summary_bbox = draw.textbbox((0, 0), change_summary, font=fonts["bold_16"])
        summary_width = summary_bbox[2] - summary_bbox[0]
        draw.text(
            (CENTER[0] - summary_width // 2, 960),
            change_summary,
            fill=(255, 255, 255, 200),
            font=fonts["bold_16"],
        )

    # Progress bar at very bottom
    progress = frame_number / max(total_frames - 1, 1)
    bar_width = int(WIDTH * progress)
    draw.rectangle([(0, HEIGHT - 4), (bar_width, HEIGHT)], fill=(255, 255, 255, 100))

    # Convert to RGB for video frames
    final = Image.new("RGB", (WIDTH, HEIGHT), (10, 10, 26))
    final.paste(img, mask=img.split()[3])
    return final


async def generate_video(
    db: AsyncSession,
    solar_system_id: UUID,
    output_path: str,
    fps: int = DEFAULT_FPS,
    hold_seconds: float = 2.0,
    transition_frames: int = DEFAULT_TRANSITION_FRAMES,
) -> str:
    """
    Generate a timeline video from all snapshots.

    Args:
        db: Database session
        solar_system_id: UUID of the solar system
        output_path: Where to save the MP4
        fps: Frames per second
        hold_seconds: How long to hold each snapshot state
        transition_frames: Number of interpolation frames between snapshots

    Returns:
        The output_path
    """
    # Fetch all snapshots ordered by creation time
    result = await db.execute(
        select(Snapshot)
        .where(Snapshot.solar_system_id == solar_system_id)
        .order_by(Snapshot.created_at.asc())
    )
    snapshots = result.scalars().all()

    if len(snapshots) < 2:
        raise ValueError("Need at least 2 snapshots to generate a video")

    hold_frames = int(hold_seconds * fps)
    total_frames = len(snapshots) * hold_frames + (len(snapshots) - 1) * transition_frames

    def _render_all_frames(tmpdir: str) -> None:
        """Render all frames to temporary directory. CPU-bound work."""
        frame_index = 0

        for i, snapshot in enumerate(snapshots):
            state = snapshot.full_state

            # Render hold frames (static display of this snapshot)
            for _ in range(hold_frames):
                frame = _render_frame(
                    state, frame_index, total_frames, snapshot.change_summary
                )
                frame.save(os.path.join(tmpdir, f"frame_{frame_index:06d}.png"))
                frame_index += 1

            # Render transition frames to next snapshot (if not last)
            if i < len(snapshots) - 1:
                next_state = snapshots[i + 1].full_state
                for t_step in range(transition_frames):
                    t = t_step / transition_frames
                    interpolated = interpolate_snapshots(state, next_state, t)
                    frame = _render_frame(interpolated, frame_index, total_frames)
                    frame.save(os.path.join(tmpdir, f"frame_{frame_index:06d}.png"))
                    frame_index += 1

        logger.info(f"Rendered {frame_index} frames to {tmpdir}")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Render frames in thread pool (CPU-bound)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _render_all_frames, tmpdir)

        # Stitch with FFmpeg (async subprocess)
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-framerate", str(fps),
            "-i", os.path.join(tmpdir, "frame_%06d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "23",
            output_path,
        ]

        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"FFmpeg failed: {error_msg}")
            raise RuntimeError(f"FFmpeg failed with exit code {process.returncode}")

        logger.info(f"Video generated: {output_path}")

    return output_path
