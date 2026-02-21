import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Person(Base):
    __tablename__ = "people"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    solar_system_id = Column(
        UUID(as_uuid=True),
        ForeignKey("solar_systems.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    avatar_url = Column(String(500), nullable=True)

    # Normalized position: both values between -1.0 and 1.0, center is (0, 0)
    x_position = Column(Float, nullable=False, default=0.5)
    y_position = Column(Float, nullable=False, default=0.0)

    # Server-computed: sqrt(x² + y²). Max theoretical value is ~1.414 (corner)
    distance_from_center = Column(Float, nullable=False, default=0.5)

    tag_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="SET NULL"),
        nullable=True,
    )

    added_at = Column(DateTime(timezone=True), server_default=func.now())
    removed_at = Column(DateTime(timezone=True), nullable=True)  # Soft delete

    # Relationships
    solar_system = relationship("SolarSystem", back_populates="people")
    tag = relationship("Tag", back_populates="people")
