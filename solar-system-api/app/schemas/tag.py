import uuid

from pydantic import BaseModel, ConfigDict


class TagCreate(BaseModel):
    name: str
    color: str
    icon: str | None = None


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    icon: str | None = None


class TagResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    icon: str | None = None
    is_predefined: bool

    model_config = ConfigDict(from_attributes=True)


class TagInPerson(BaseModel):
    """Minimal tag info embedded in person responses."""
    name: str
    color: str
    icon: str | None = None

    model_config = ConfigDict(from_attributes=True)
