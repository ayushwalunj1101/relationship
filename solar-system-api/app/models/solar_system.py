import uuid

from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SolarSystem(Base):
    __tablename__ = "solar_systems"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Frontend-controlled visual configuration (stored as-is)
    theme = Column(JSONB, nullable=False, default=dict, server_default="{}")

    # Relationships
    user = relationship("User", back_populates="solar_system")
    people = relationship("Person", back_populates="solar_system", lazy="selectin")
    tags = relationship("Tag", back_populates="solar_system", lazy="selectin")
    snapshots = relationship(
        "Snapshot", back_populates="solar_system", order_by="Snapshot.created_at"
    )
