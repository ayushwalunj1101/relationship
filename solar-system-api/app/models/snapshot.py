import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    solar_system_id = Column(
        UUID(as_uuid=True),
        ForeignKey("solar_systems.id", ondelete="CASCADE"),
        nullable=False,
    )

    # JSONB column storing the FULL system state at this point in time
    full_state = Column(JSONB, nullable=False)

    change_type = Column(String(30), nullable=False)
    # Valid: "person_added", "person_removed", "person_moved",
    #        "person_tag_changed", "system_created"

    change_summary = Column(String(255), nullable=False)
    # Human-readable: "Added Riya as Friend", "Moved Aman closer", "Removed Karan"

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    solar_system = relationship("SolarSystem", back_populates="snapshots")
