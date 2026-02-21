from datetime import datetime

from pydantic import BaseModel


class ImageGenerationResponse(BaseModel):
    image_url: str
    generated_at: datetime


class VideoGenerationRequest(BaseModel):
    fps: int = 30
    duration_per_snapshot: float = 2.0
    transition_frames: int = 15


class VideoGenerationResponse(BaseModel):
    video_url: str
    generated_at: datetime
    snapshot_count: int
