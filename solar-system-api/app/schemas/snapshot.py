import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SnapshotListItem(BaseModel):
    id: uuid.UUID
    change_type: str
    change_summary: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SnapshotDetail(BaseModel):
    id: uuid.UUID
    solar_system_id: uuid.UUID
    full_state: dict[str, Any]
    change_type: str
    change_summary: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SnapshotPaginatedResponse(BaseModel):
    snapshots: list[SnapshotListItem]
    total: int
    page: int
    per_page: int
