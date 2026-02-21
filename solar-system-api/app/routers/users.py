from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.solar_system import SolarSystem
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.services.snapshot_service import capture_snapshot

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a user. Auto-creates their SolarSystem and initial snapshot."""
    # 1. Create user
    user = User(
        name=user_data.name,
        email=user_data.email,
        avatar_url=user_data.avatar_url,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # 2. Auto-create solar system
    solar_system = SolarSystem(user_id=user.id)
    db.add(solar_system)
    await db.flush()
    await db.refresh(solar_system)

    # 3. Create initial snapshot
    await capture_snapshot(
        db,
        solar_system.id,
        "system_created",
        f"Solar system created for {user.name}",
    )

    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        avatar_url=user.avatar_url,
        solar_system_id=solar_system.id,
        created_at=user.created_at,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a user by ID."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.solar_system))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        avatar_url=user.avatar_url,
        solar_system_id=user.solar_system.id if user.solar_system else None,
        created_at=user.created_at,
    )
