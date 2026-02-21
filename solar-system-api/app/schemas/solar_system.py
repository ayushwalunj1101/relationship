import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.person import PersonResponse
from app.schemas.tag import TagResponse


class SolarSystemUserInfo(BaseModel):
    id: uuid.UUID
    name: str
    avatar_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SolarSystemStats(BaseModel):
    total_people: int
    average_distance: float
    closest_person: dict[str, Any] | None = None
    furthest_person: dict[str, Any] | None = None
    tag_distribution: dict[str, int]
    relationship_score_distribution: dict[str, int]
    timeline_activity: list[dict[str, Any]]


class ThemeUpdate(BaseModel):
    theme: dict[str, Any]


class SolarSystemResponse(BaseModel):
    id: uuid.UUID
    user: SolarSystemUserInfo
    people: list[PersonResponse]
    tags: list[TagResponse]
    created_at: datetime
    updated_at: datetime
    theme: dict[str, Any] = {}
    stats: SolarSystemStats | None = None
    last_activity: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
