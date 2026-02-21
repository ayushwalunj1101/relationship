import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.tag import TagInPerson


class PersonCreate(BaseModel):
    name: str
    x_position: float
    y_position: float
    tag_id: uuid.UUID | None = None
    avatar_url: str | None = None

    @field_validator("x_position", "y_position")
    @classmethod
    def validate_position(cls, v: float) -> float:
        if not -1.0 <= v <= 1.0:
            raise ValueError("Position must be between -1.0 and 1.0")
        return round(v, 6)


class PersonUpdate(BaseModel):
    name: str | None = None
    x_position: float | None = None
    y_position: float | None = None
    tag_id: uuid.UUID | None = None
    avatar_url: str | None = None

    @field_validator("x_position", "y_position")
    @classmethod
    def validate_position(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if not -1.0 <= v <= 1.0:
            raise ValueError("Position must be between -1.0 and 1.0")
        return round(v, 6)


class PersonResponse(BaseModel):
    id: uuid.UUID
    name: str
    x_position: float
    y_position: float
    distance_from_center: float
    tag: TagInPerson | None = None
    avatar_url: str | None = None
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)
