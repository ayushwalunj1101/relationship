import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.routers import users, solar_system as solar_system_router, people, tags, snapshots, generation
from app.utils.seed_tags import seed_predefined_tags


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables
    from app.models import User, SolarSystem, Person, Tag, Snapshot  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed predefined tags
    await seed_predefined_tags()

    # Ensure generated directories exist
    os.makedirs(os.path.join(settings.GENERATED_DIR, "images"), exist_ok=True)
    os.makedirs(os.path.join(settings.GENERATED_DIR, "videos"), exist_ok=True)

    yield


app = FastAPI(title="Relationship Solar System API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router)
app.include_router(solar_system_router.router)
app.include_router(people.router)
app.include_router(tags.router)
app.include_router(snapshots.router)
app.include_router(generation.router)

# Serve generated files (images, videos) as static files
# Must come AFTER all include_router calls
app.mount("/generated", StaticFiles(directory=settings.GENERATED_DIR), name="generated")
