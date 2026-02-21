from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.person import Person
from app.models.tag import Tag
from app.schemas.tag import TagCreate, TagResponse, TagUpdate
from app.services.solar_system_service import get_solar_system_by_user

router = APIRouter(tags=["tags"])


@router.get("/api/tags/predefined", response_model=list[TagResponse])
async def get_predefined_tags(db: AsyncSession = Depends(get_db)):
    """Get all predefined (global) tags."""
    result = await db.execute(
        select(Tag).where(Tag.is_predefined == True)  # noqa: E712
    )
    return result.scalars().all()


@router.post(
    "/api/solar-system/{user_id}/tags",
    response_model=TagResponse,
    status_code=201,
)
async def create_custom_tag(
    user_id: UUID,
    tag_data: TagCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a custom tag for a user's solar system."""
    ss = await get_solar_system_by_user(db, user_id)

    tag = Tag(
        solar_system_id=ss.id,
        name=tag_data.name,
        color=tag_data.color,
        icon=tag_data.icon,
        is_predefined=False,
    )
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return tag


@router.patch(
    "/api/solar-system/{user_id}/tags/{tag_id}",
    response_model=TagResponse,
)
async def update_tag(
    user_id: UUID,
    tag_id: UUID,
    tag_data: TagUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a custom tag. Returns 403 for predefined tags."""
    await get_solar_system_by_user(db, user_id)  # Verify user exists

    tag = await db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if tag.is_predefined:
        raise HTTPException(status_code=403, detail="Cannot modify predefined tags")

    if tag_data.name is not None:
        tag.name = tag_data.name
    if tag_data.color is not None:
        tag.color = tag_data.color
    if tag_data.icon is not None:
        tag.icon = tag_data.icon

    await db.flush()
    await db.refresh(tag)
    return tag


@router.delete("/api/solar-system/{user_id}/tags/{tag_id}")
async def delete_tag(
    user_id: UUID,
    tag_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom tag. Returns 403 for predefined tags. Unlinks people using this tag."""
    await get_solar_system_by_user(db, user_id)  # Verify user exists

    tag = await db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if tag.is_predefined:
        raise HTTPException(status_code=403, detail="Cannot delete predefined tags")

    # Unlink all people using this tag
    await db.execute(
        update(Person).where(Person.tag_id == tag_id).values(tag_id=None)
    )

    await db.delete(tag)
    await db.flush()
    return {"message": "Tag deleted"}
