import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.tag import TagInPerson


def _validate_hex_color(v: str | None) -> str | None:
    if v is None:
        return v
    if len(v) != 7 or not v.startswith("#"):
        raise ValueError("Color must be a 7-character hex string like '#FF5733'")
    try:
        int(v[1:], 16)
    except ValueError:
        raise ValueError("Color must be a valid hex color")
    return v.upper()


def _validate_positive_float(v: float | None) -> float | None:
    if v is None:
        return v
    if v <= 0:
        raise ValueError("Value must be positive")
    return round(v, 4)


class PersonCreate(BaseModel):
    name: str
    x_position: float
    y_position: float
    tag_id: uuid.UUID | None = None
    avatar_url: str | None = None
    orbit_speed: float = 1.0
    planet_size: float = 1.0
    custom_color: str | None = None
    notes: str | None = None
    relationship_score: int | None = Field(default=None, ge=0, le=100)

    @field_validator("x_position", "y_position")
    @classmethod
    def validate_position(cls, v: float) -> float:
        if not -1.0 <= v <= 1.0:
            raise ValueError("Position must be between -1.0 and 1.0")
        return round(v, 6)

    @field_validator("custom_color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        return _validate_hex_color(v)

    @field_validator("orbit_speed", "planet_size")
    @classmethod
    def validate_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Value must be positive")
        return round(v, 4)


class PersonUpdate(BaseModel):
    name: str | None = None
    x_position: float | None = None
    y_position: float | None = None
    tag_id: uuid.UUID | None = None
    avatar_url: str | None = None
    orbit_speed: float | None = None
    planet_size: float | None = None
    custom_color: str | None = None
    notes: str | None = None
    relationship_score: int | None = Field(default=None, ge=0, le=100)

    @field_validator("x_position", "y_position")
    @classmethod
    def validate_position(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if not -1.0 <= v <= 1.0:
            raise ValueError("Position must be between -1.0 and 1.0")
        return round(v, 6)

    @field_validator("custom_color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        return _validate_hex_color(v)

    @field_validator("orbit_speed", "planet_size")
    @classmethod
    def validate_positive(cls, v: float | None) -> float | None:
        return _validate_positive_float(v)


class PersonResponse(BaseModel):
    id: uuid.UUID
    name: str
    x_position: float
    y_position: float
    distance_from_center: float
    tag: TagInPerson | None = None
    avatar_url: str | None = None
    added_at: datetime
    orbit_speed: float
    planet_size: float
    custom_color: str | None = None
    notes: str | None = None
    relationship_score: int | None = None

    model_config = ConfigDict(from_attributes=True)


class BulkPositionItem(BaseModel):
    person_id: uuid.UUID
    x_position: float
    y_position: float

    @field_validator("x_position", "y_position")
    @classmethod
    def validate_position(cls, v: float) -> float:
        if not -1.0 <= v <= 1.0:
            raise ValueError("Position must be between -1.0 and 1.0")
        return round(v, 6)


class BulkPositionUpdate(BaseModel):
    updates: list[BulkPositionItem]
