from sqlalchemy import select

from app.database import async_session
from app.models.tag import Tag

PREDEFINED_TAGS = [
    {"name": "Partner", "color": "#FF6B6B", "icon": "\u2764\ufe0f"},
    {"name": "Family", "color": "#FFD93D", "icon": "\U0001f3e0"},
    {"name": "Close Friend", "color": "#4ECDC4", "icon": "\U0001f91d"},
    {"name": "Friend", "color": "#45B7D1", "icon": "\U0001f44b"},
    {"name": "Colleague", "color": "#96CEB4", "icon": "\U0001f4bc"},
    {"name": "Mentor", "color": "#DDA0DD", "icon": "\U0001f31f"},
    {"name": "Acquaintance", "color": "#95A5A6", "icon": "\U0001f464"},
]


async def seed_predefined_tags() -> None:
    """Seed predefined tags if they don't already exist. Safe to call on every startup."""
    async with async_session() as session:
        result = await session.execute(
            select(Tag).where(Tag.is_predefined == True)  # noqa: E712
        )
        existing_tags = result.scalars().all()
        existing_names = {t.name for t in existing_tags}

        for tag_data in PREDEFINED_TAGS:
            if tag_data["name"] not in existing_names:
                tag = Tag(
                    name=tag_data["name"],
                    color=tag_data["color"],
                    icon=tag_data["icon"],
                    is_predefined=True,
                    solar_system_id=None,
                )
                session.add(tag)

        await session.commit()
