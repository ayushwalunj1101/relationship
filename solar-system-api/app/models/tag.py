import uuid

from sqlalchemy import Boolean, Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    solar_system_id = Column(
        UUID(as_uuid=True),
        ForeignKey("solar_systems.id", ondelete="CASCADE"),
        nullable=True,
    )
    # solar_system_id is NULL for predefined/global tags

    name = Column(String(50), nullable=False)
    color = Column(String(7), nullable=False)  # Hex color like "#FF5733"
    icon = Column(String(50), nullable=True)  # Optional emoji or icon identifier
    is_predefined = Column(Boolean, default=False)

    # Relationships
    solar_system = relationship("SolarSystem", back_populates="tags")
    people = relationship("Person", back_populates="tag")
