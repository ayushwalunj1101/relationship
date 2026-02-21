import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.person import PersonResponse
from app.schemas.tag import TagResponse


class SolarSystemUserInfo(BaseModel):
    id: uuid.UUID
    name: str
    avatar_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SolarSystemResponse(BaseModel):
    id: uuid.UUID
    user: SolarSystemUserInfo
    people: list[PersonResponse]
    tags: list[TagResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
