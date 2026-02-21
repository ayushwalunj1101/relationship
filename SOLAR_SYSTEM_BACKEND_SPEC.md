# Relationship Solar System — Backend Implementation Spec

## Overview

Build a FastAPI backend for a "Relationship Solar System" feature where a user is at the center and can add people (planets) around them, tag them by relationship type, freely position them on a 2D plane (distance from center = emotional closeness), and generate shareable images and timeline videos.

This is a **hackathon project** — no JWT auth needed. User identification is done via `user_id` passed as a path/query parameter. Focus on correctness, clean API design, and working image/video generation.

---

## Tech Stack

- **Runtime:** Python 3.11+
- **Framework:** FastAPI (async)
- **ORM:** SQLAlchemy 2.0 with async support (asyncpg driver)
- **Database:** PostgreSQL 15+ (use JSONB for snapshot state storage)
- **Migrations:** Alembic (async-compatible)
- **Validation:** Pydantic v2
- **Image Generation:** Pillow (PIL)
- **Video Generation:** Pillow (frame rendering) + FFmpeg (subprocess, stitching frames into MP4)
- **Server:** Uvicorn

### Required Python Packages

```
fastapi
uvicorn[standard]
sqlalchemy[asyncio]
asyncpg
alembic
pydantic
pydantic-settings
pillow
python-dotenv
aiofiles
```

### System Dependencies

```
postgresql
ffmpeg
```

---

## Project Structure

```
solar-system-api/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, lifespan, CORS, router includes
│   ├── config.py                # Settings via pydantic-settings (DATABASE_URL, etc.)
│   ├── database.py              # Async engine, sessionmaker, Base, get_db dependency
│   │
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── __init__.py          # Import all models here for Alembic discovery
│   │   ├── user.py
│   │   ├── solar_system.py
│   │   ├── person.py
│   │   ├── tag.py
│   │   └── snapshot.py
│   │
│   ├── schemas/                 # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── solar_system.py
│   │   ├── person.py
│   │   ├── tag.py
│   │   ├── snapshot.py
│   │   └── generation.py        # Schemas for image/video generation responses
│   │
│   ├── routers/                 # API route handlers (thin — delegate to services)
│   │   ├── __init__.py
│   │   ├── users.py
│   │   ├── solar_system.py
│   │   ├── people.py
│   │   ├── tags.py
│   │   ├── snapshots.py
│   │   └── generation.py        # Image + video generation endpoints
│   │
│   ├── services/                # Business logic layer
│   │   ├── __init__.py
│   │   ├── solar_system_service.py
│   │   ├── snapshot_service.py
│   │   ├── image_generator.py   # Strava-style image generation via Pillow
│   │   └── video_generator.py   # Timeline video generation via Pillow + FFmpeg
│   │
│   └── utils/
│       ├── __init__.py
│       ├── seed_tags.py         # Predefined tags seeder (run on startup)
│       └── interpolation.py     # Position lerping helper for smooth video transitions
│
├── assets/
│   └── fonts/
│       └── Inter-Regular.ttf    # Download Inter font for image rendering
│       └── Inter-Bold.ttf
│
├── generated/                   # Output directory for generated images and videos
│   ├── images/
│   └── videos/
│
├── migrations/                  # Alembic migrations directory
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── alembic.ini
├── requirements.txt
├── .env
└── README.md
```

---

## Database Models

### CRITICAL DESIGN DECISIONS
- All positions are **normalized floats between -1.0 and 1.0**. Center is (0, 0). The frontend scales to its canvas size. Image/video generators scale to their own canvas size.
- `distance_from_center` is **computed server-side** on every position save using `sqrt(x² + y²)` and stored as a column for easy querying.
- Snapshots store **full system state as JSONB**, not diffs. This makes video/image generation trivial — each snapshot is self-contained.
- People are **soft-deleted** (via `removed_at` timestamp) so they appear in historical snapshots and timeline videos with a "departed" status.

### User Model

```python
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True, unique=True)
    avatar_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    solar_system = relationship("SolarSystem", back_populates="user", uselist=False)
```

### SolarSystem Model

Each user has exactly ONE solar system.

```python
class SolarSystem(Base):
    __tablename__ = "solar_systems"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="solar_system")
    people = relationship("Person", back_populates="solar_system", lazy="selectin")
    tags = relationship("Tag", back_populates="solar_system", lazy="selectin")
    snapshots = relationship("Snapshot", back_populates="solar_system", order_by="Snapshot.created_at")
```

### Person Model (Planets)

```python
class Person(Base):
    __tablename__ = "people"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    solar_system_id = Column(UUID(as_uuid=True), ForeignKey("solar_systems.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    avatar_url = Column(String(500), nullable=True)

    # Normalized position: both values between -1.0 and 1.0, center is (0, 0)
    x_position = Column(Float, nullable=False, default=0.5)
    y_position = Column(Float, nullable=False, default=0.0)

    # Server-computed: sqrt(x² + y²). Max theoretical value is ~1.414 (corner)
    distance_from_center = Column(Float, nullable=False, default=0.5)

    tag_id = Column(UUID(as_uuid=True), ForeignKey("tags.id", ondelete="SET NULL"), nullable=True)

    added_at = Column(DateTime(timezone=True), server_default=func.now())
    removed_at = Column(DateTime(timezone=True), nullable=True)  # Soft delete

    # Relationships
    solar_system = relationship("SolarSystem", back_populates="people")
    tag = relationship("Tag", back_populates="people")
```

**Server-side computation on every create/update:**
```python
import math
person.distance_from_center = math.sqrt(person.x_position ** 2 + person.y_position ** 2)
```

### Tag Model

```python
class Tag(Base):
    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    solar_system_id = Column(UUID(as_uuid=True), ForeignKey("solar_systems.id", ondelete="CASCADE"), nullable=True)
    # solar_system_id is NULL for predefined/global tags

    name = Column(String(50), nullable=False)
    color = Column(String(7), nullable=False)  # Hex color like "#FF5733"
    icon = Column(String(50), nullable=True)    # Optional emoji or icon identifier
    is_predefined = Column(Boolean, default=False)

    # Relationships
    solar_system = relationship("SolarSystem", back_populates="tags")
    people = relationship("Person", back_populates="tag")
```

### Snapshot Model

```python
class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    solar_system_id = Column(UUID(as_uuid=True), ForeignKey("solar_systems.id", ondelete="CASCADE"), nullable=False)

    # JSONB column storing the FULL system state at this point in time
    full_state = Column(JSONB, nullable=False)

    change_type = Column(String(30), nullable=False)
    # Valid change_type values: "person_added", "person_removed", "person_moved", "person_tag_changed", "system_created"

    change_summary = Column(String(255), nullable=False)
    # Human-readable: "Added Riya as Friend", "Moved Aman closer", "Removed Karan"

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    solar_system = relationship("SolarSystem", back_populates="snapshots")
```

### Snapshot `full_state` JSON Structure

This is what gets stored in the JSONB column. **Every snapshot is a complete, self-contained picture.**

```json
{
  "user": {
    "id": "uuid",
    "name": "Ayush",
    "avatar_url": "..."
  },
  "people": [
    {
      "id": "uuid",
      "name": "Riya",
      "x_position": 0.3,
      "y_position": -0.2,
      "distance_from_center": 0.36,
      "tag": {
        "name": "Partner",
        "color": "#FF6B6B",
        "icon": "❤️"
      },
      "avatar_url": "...",
      "is_active": true
    },
    {
      "id": "uuid",
      "name": "Karan",
      "x_position": -0.7,
      "y_position": 0.5,
      "distance_from_center": 0.86,
      "tag": {
        "name": "Friend",
        "color": "#4ECDC4",
        "icon": "👋"
      },
      "avatar_url": null,
      "is_active": true
    }
  ],
  "tags_summary": {
    "Partner": 1,
    "Friend": 3,
    "Family": 2
  },
  "total_active_people": 6,
  "snapshot_timestamp": "2025-02-21T10:30:00Z"
}
```

---

## Predefined Tags (Seed Data)

Seed these on application startup if they don't exist. Set `is_predefined = True` and `solar_system_id = NULL`.

```python
PREDEFINED_TAGS = [
    {"name": "Partner",       "color": "#FF6B6B", "icon": "❤️"},
    {"name": "Family",        "color": "#FFD93D", "icon": "🏠"},
    {"name": "Close Friend",  "color": "#4ECDC4", "icon": "🤝"},
    {"name": "Friend",        "color": "#45B7D1", "icon": "👋"},
    {"name": "Colleague",     "color": "#96CEB4", "icon": "💼"},
    {"name": "Mentor",        "color": "#DDA0DD", "icon": "🌟"},
    {"name": "Acquaintance",  "color": "#95A5A6", "icon": "👤"},
]
```

Seed function should run inside the app lifespan (startup event). Check if predefined tags exist first to avoid duplicates on restart.

---

## API Endpoints — Full Contract

### Users

```
POST /api/users
  Request:  { "name": "Ayush", "email": "ayush@example.com", "avatar_url": "..." }
  Response: { "id": "uuid", "name": "Ayush", "email": "...", "avatar_url": "...", "created_at": "..." }
  Notes:    Creates user. Email is optional. This also auto-creates their SolarSystem.

GET /api/users/{user_id}
  Response: { "id": "uuid", "name": "...", "email": "...", "solar_system_id": "uuid", ... }
```

**IMPORTANT:** When a user is created via `POST /api/users`, the backend should AUTOMATICALLY create a SolarSystem for them and create the first snapshot with `change_type: "system_created"` and an empty people array. Every user always has exactly one solar system.

### Solar System

```
GET /api/solar-system/{user_id}
  Response: Full solar system state including all active people (where removed_at IS NULL) and all tags (predefined + custom).
  {
    "id": "uuid",
    "user": { "id": "...", "name": "..." },
    "people": [ { "id": "...", "name": "...", "x_position": 0.3, "y_position": -0.2, "distance_from_center": 0.36, "tag": {...}, ... } ],
    "tags": [ { "id": "...", "name": "Partner", "color": "#FF6B6B", "is_predefined": true }, ... ],
    "created_at": "...",
    "updated_at": "..."
  }
  Notes: This is the primary endpoint the frontend calls to render the solar system. It returns ONLY active people (removed_at IS NULL).
```

### People (Planets)

```
POST /api/solar-system/{user_id}/people
  Request:  { "name": "Riya", "x_position": 0.3, "y_position": -0.2, "tag_id": "uuid", "avatar_url": "..." }
  Response: Created person object + snapshot created
  Behavior:
    1. Validate x_position and y_position are between -1.0 and 1.0
    2. Compute distance_from_center = sqrt(x² + y²)
    3. Save person
    4. Create snapshot with change_type="person_added", change_summary="Added Riya as Partner"
    5. Return person

PATCH /api/solar-system/{user_id}/people/{person_id}
  Request:  { "x_position": 0.1, "y_position": -0.1, "tag_id": "uuid" }  (all fields optional)
  Response: Updated person object
  Behavior:
    1. If position changed: recompute distance_from_center, create snapshot with change_type="person_moved"
    2. If tag changed: create snapshot with change_type="person_tag_changed"
    3. If both changed: create snapshot with change_type="person_moved" (position takes precedence in change_type)
    4. change_summary should be descriptive: "Moved Riya closer" (if distance decreased) or "Moved Riya further" (if distance increased) or "Changed Riya's tag to Family"

DELETE /api/solar-system/{user_id}/people/{person_id}
  Response: { "message": "Person removed", "id": "uuid" }
  Behavior:
    1. Set removed_at = now() (SOFT DELETE, do NOT actually delete the row)
    2. Create snapshot with change_type="person_removed", change_summary="Removed Karan"
    3. The person will no longer appear in GET /api/solar-system/{user_id} but WILL appear in historical snapshots
```

### Tags

```
GET /api/tags/predefined
  Response: [ { "id": "...", "name": "Partner", "color": "#FF6B6B", "icon": "❤️", "is_predefined": true }, ... ]

POST /api/solar-system/{user_id}/tags
  Request:  { "name": "Gym Buddy", "color": "#FF9F43", "icon": "💪" }
  Response: Created tag object
  Notes:    Custom tag. Set solar_system_id to user's solar system, is_predefined = false.

PATCH /api/solar-system/{user_id}/tags/{tag_id}
  Request:  { "name": "...", "color": "...", "icon": "..." } (all optional)
  Response: Updated tag
  Notes:    Can only update custom tags (is_predefined = false). Return 403 for predefined tags.

DELETE /api/solar-system/{user_id}/tags/{tag_id}
  Response: { "message": "Tag deleted" }
  Notes:    Can only delete custom tags. Set tag_id to NULL for all people using this tag before deleting.
```

### Snapshots

```
GET /api/solar-system/{user_id}/snapshots
  Query Params: ?page=1&per_page=20
  Response: Paginated list of snapshots (id, change_type, change_summary, created_at) — WITHOUT full_state for performance.
  {
    "snapshots": [ { "id": "...", "change_type": "person_added", "change_summary": "Added Riya as Partner", "created_at": "..." } ],
    "total": 45,
    "page": 1,
    "per_page": 20
  }

GET /api/solar-system/{user_id}/snapshots/{snapshot_id}
  Response: Full snapshot including full_state JSON.
  Notes:    Use this to view the exact state of the solar system at a specific point in time.
```

### Generation (Image + Video)

```
POST /api/solar-system/{user_id}/generate-image
  Request:  {} (no body needed — generates from current state)
  Response: { "image_url": "/generated/images/{filename}.png", "generated_at": "..." }
  Behavior: Generates Strava-style shareable image from current solar system state. See Image Generation section.

POST /api/solar-system/{user_id}/generate-video
  Request:  { "fps": 30, "duration_per_snapshot": 2.0, "transition_frames": 15 } (all optional with defaults)
  Response: { "video_url": "/generated/videos/{filename}.mp4", "generated_at": "...", "snapshot_count": 12 }
  Behavior: Generates timeline video from all snapshots. See Video Generation section.
```

Serve the `generated/` directory as static files in FastAPI:
```python
from fastapi.staticfiles import StaticFiles
app.mount("/generated", StaticFiles(directory="generated"), name="generated")
```

---

## Service Layer — Business Logic

### Snapshot Service (`snapshot_service.py`)

This is the **most critical service**. Every mutation calls it.

```python
async def capture_snapshot(
    db: AsyncSession,
    solar_system_id: UUID,
    change_type: str,
    change_summary: str
) -> Snapshot:
    """
    Captures the FULL current state of the solar system and saves it as a snapshot.
    Called after every mutation (add/move/remove person, etc.)
    """
    # 1. Fetch solar system with all active people (removed_at IS NULL) and their tags
    # 2. Fetch the user
    # 3. Build the full_state JSON (see schema above)
    # 4. Create and save Snapshot
    # 5. Return snapshot
```

**Key points:**
- Always fetch fresh data AFTER the mutation has been committed
- Include ALL active people, not just the one that changed
- Include the tags_summary count
- Include snapshot_timestamp as ISO string

### Solar System Service (`solar_system_service.py`)

```python
async def get_full_solar_system(db: AsyncSession, user_id: UUID) -> dict:
    """Returns the complete current state for the frontend."""
    # Fetch solar system with eager-loaded people (active only) and tags
    # Return structured response

async def add_person(db: AsyncSession, user_id: UUID, person_data: PersonCreate) -> Person:
    """Add a person and create snapshot."""
    # 1. Validate positions are in [-1.0, 1.0]
    # 2. Compute distance_from_center
    # 3. Save person to DB
    # 4. Determine tag name for summary
    # 5. Call capture_snapshot(change_type="person_added", summary=f"Added {name} as {tag_name}")
    # 6. Return created person

async def update_person(db: AsyncSession, user_id: UUID, person_id: UUID, update_data: PersonUpdate) -> Person:
    """Update a person's position/tag and create snapshot."""
    # 1. Fetch existing person
    # 2. Track what changed (position? tag? both?)
    # 3. If position changed: recompute distance, determine if closer/further
    # 4. Update fields
    # 5. Create appropriate snapshot
    # 6. Return updated person

async def remove_person(db: AsyncSession, user_id: UUID, person_id: UUID) -> None:
    """Soft-delete a person and create snapshot."""
    # 1. Set removed_at = now()
    # 2. Call capture_snapshot(change_type="person_removed", summary=f"Removed {name}")
```

---

## Image Generation — Strava-Style (`image_generator.py`)

### Canvas Specs
- **Size:** 1080 × 1080 pixels (square, Instagram-ready)
- **Center of canvas:** (540, 540) — this is where the user sits
- **Coordinate mapping:** Normalized (-1, 1) → pixel. Formula: `pixel_x = 540 + (normalized_x * 450)`, `pixel_y = 540 + (normalized_y * 450)`. The 450 gives padding (90px on each side).

### Visual Design Specification

**Background:**
- Base: Deep space dark (`#0A0A1A`)
- Radial gradient from center: subtle dark blue (`#0F1B3D`) fading to the base color
- Star field: ~150 randomly placed small white dots (1-2px), with ~20 slightly larger dots (2-3px) at 50% opacity for depth. Use a FIXED random seed based on the solar_system_id so stars are consistent across generations.

**Orbital Rings (Reference Circles):**
- Draw 4-5 concentric circles centered at (540, 540)
- Radii: 100, 200, 300, 400, 450 pixels
- Color: White at 6-8% opacity (`#FFFFFF` with alpha ~15-20)
- Line width: 1px
- These are purely visual guides — people can be anywhere, not just on rings

**Center (User):**
- Circle: 40px radius, filled with a warm gradient (or solid `#FFD700` gold)
- Glow effect: Draw the same circle 3 more times at radii 44, 48, 52 with decreasing opacity (like a bloom)
- Name below: User's name in Inter Bold 16px, white, centered below the circle
- Label above: Small "YOU" text in Inter Regular 10px, white at 60% opacity

**People (Planets):**
- Circle: 20px radius, filled with their TAG COLOR
- Glow effect: Same bloom technique as user but smaller (22, 24, 26 radii)
- Name: Person's name in Inter Regular 12px, white, positioned below their circle
- Tag icon: The emoji icon drawn above or beside the circle
- Connection line: Draw a subtle line from center to each person — color it with the tag color at 15% opacity, 1px width

**Stats Bar (Bottom):**
- Background: Semi-transparent dark strip at the bottom (full width, 80px tall, `#000000` at 60% opacity)
- Left-aligned text:
  - Line 1: "{total_people} people in my orbit" — Inter Bold 18px, white
  - Line 2: Tag breakdown — "3 Friends · 2 Family · 1 Partner" — Inter Regular 13px, white at 70%
- Right-aligned: Date — "Feb 2025" — Inter Regular 13px, white at 50%

**Title/Branding (Top):**
- Top-center: "My Solar System" or the app name — Inter Bold 20px, white at 80%
- Subtle decorative line below: 60px wide, 1px, white at 20%

### Implementation Approach

```python
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, random

async def generate_strava_image(solar_system_state: dict, output_path: str) -> str:
    """
    Generates a 1080x1080 Strava-style image from the current solar system state.
    Returns the file path of the generated image.
    """
    WIDTH, HEIGHT = 1080, 1080
    CENTER = (540, 540)
    SCALE = 450  # normalized coords * SCALE = pixel offset from center

    img = Image.new("RGBA", (WIDTH, HEIGHT), (10, 10, 26, 255))
    draw = ImageDraw.Draw(img)

    # 1. Draw radial background gradient (use multiple concentric filled circles with decreasing opacity)
    # 2. Draw star field (fixed seed from solar_system_id)
    # 3. Draw orbital reference rings
    # 4. Draw connection lines from center to each person
    # 5. Draw each person as a glowing planet
    # 6. Draw user at center with glow
    # 7. Draw stats bar at bottom
    # 8. Draw title at top

    # For glow effects: create a separate layer, draw the circle, apply GaussianBlur, composite onto main image
    glow_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    # Draw circle on glow_layer, blur it, then: img = Image.alpha_composite(img, glow_layer)

    img.save(output_path, "PNG", quality=95)
    return output_path
```

### Font Loading

```python
# Load fonts at module level
FONT_DIR = "assets/fonts"
font_bold_20 = ImageFont.truetype(f"{FONT_DIR}/Inter-Bold.ttf", 20)
font_bold_18 = ImageFont.truetype(f"{FONT_DIR}/Inter-Bold.ttf", 18)
font_bold_16 = ImageFont.truetype(f"{FONT_DIR}/Inter-Bold.ttf", 16)
font_regular_13 = ImageFont.truetype(f"{FONT_DIR}/Inter-Regular.ttf", 13)
font_regular_12 = ImageFont.truetype(f"{FONT_DIR}/Inter-Regular.ttf", 12)
font_regular_10 = ImageFont.truetype(f"{FONT_DIR}/Inter-Regular.ttf", 10)
```

**Download Inter font TTF files and place in `assets/fonts/`.** Google Fonts provides them: https://fonts.google.com/specimen/Inter

---

## Video Generation — Timeline (`video_generator.py`)

### Pipeline Overview

```
1. Fetch ALL snapshots for the solar system, ordered by created_at ASC
2. For each snapshot, render a frame (same visual style as the Strava image)
3. Between consecutive snapshots, generate INTERPOLATION frames (lerp positions)
4. Add text overlay per snapshot: change_summary + timestamp
5. Pipe all frames to FFmpeg → output MP4
```

### Parameters (with defaults)

```python
FPS = 30
HOLD_FRAMES = 60          # Hold each snapshot state for 2 seconds (60 frames at 30fps)
TRANSITION_FRAMES = 15     # 0.5 seconds of smooth transition between snapshots
FRAME_WIDTH = 1080
FRAME_HEIGHT = 1080
```

### Interpolation Logic (`utils/interpolation.py`)

```python
def lerp(start: float, end: float, t: float) -> float:
    """Linear interpolation. t ranges from 0.0 to 1.0."""
    return start + (end - start) * t

def ease_in_out(t: float) -> float:
    """Smooth easing function for more natural motion."""
    return t * t * (3 - 2 * t)  # Hermite interpolation

def interpolate_snapshots(snapshot_a: dict, snapshot_b: dict, t: float) -> dict:
    """
    Creates an intermediate state between two snapshots at time t (0.0 to 1.0).
    - People present in both: lerp their positions
    - People only in A (removed): fade them out (reduce alpha as t increases)
    - People only in B (added): fade them in (increase alpha as t increases)
    """
    eased_t = ease_in_out(t)

    # Match people by ID between snapshots
    people_a = {p["id"]: p for p in snapshot_a["people"]}
    people_b = {p["id"]: p for p in snapshot_b["people"]}

    all_ids = set(people_a.keys()) | set(people_b.keys())

    interpolated_people = []
    for pid in all_ids:
        if pid in people_a and pid in people_b:
            # Present in both — lerp position
            pa, pb = people_a[pid], people_b[pid]
            interpolated_people.append({
                **pb,
                "x_position": lerp(pa["x_position"], pb["x_position"], eased_t),
                "y_position": lerp(pa["y_position"], pb["y_position"], eased_t),
                "alpha": 1.0
            })
        elif pid in people_a:
            # Removed — fade out
            interpolated_people.append({**people_a[pid], "alpha": 1.0 - eased_t})
        else:
            # Added — fade in
            interpolated_people.append({**people_b[pid], "alpha": eased_t})

    return {
        **snapshot_b,
        "people": interpolated_people,
    }
```

### Frame Rendering

Reuse the SAME drawing logic from image generation, but with these additions:
- Accept an `alpha` field per person to handle fade in/out
- Add a text overlay at the bottom showing `change_summary` and timestamp
- Add a subtle progress bar at the very bottom showing position in the timeline

```python
def render_frame(state: dict, frame_number: int, total_frames: int, change_summary: str = None) -> Image.Image:
    """
    Renders a single frame. Nearly identical to strava image generation,
    but with:
    - Per-person alpha support (for fade in/out during transitions)
    - Change summary text overlay
    - Timeline progress bar
    """
    # ... same drawing logic as image_generator ...
    # At bottom: show change_summary text if provided
    # At very bottom: thin progress bar (frame_number / total_frames)
    return img
```

### FFmpeg Stitching

```python
import subprocess, os, tempfile

async def generate_video(solar_system_id: UUID, db: AsyncSession, output_path: str, fps: int = 30) -> str:
    """Generates timeline video from all snapshots."""

    # 1. Fetch all snapshots ordered by created_at
    snapshots = await get_all_snapshots(db, solar_system_id)

    if len(snapshots) < 2:
        raise ValueError("Need at least 2 snapshots to generate a video")

    # 2. Create temp directory for frames
    with tempfile.TemporaryDirectory() as tmpdir:
        frame_index = 0

        for i, snapshot in enumerate(snapshots):
            state = snapshot.full_state

            # Render hold frames (static display of this snapshot)
            for _ in range(HOLD_FRAMES):
                frame = render_frame(state, frame_index, total_frames, snapshot.change_summary)
                frame.save(os.path.join(tmpdir, f"frame_{frame_index:06d}.png"))
                frame_index += 1

            # Render transition frames to next snapshot (if not last)
            if i < len(snapshots) - 1:
                next_state = snapshots[i + 1].full_state
                for t_step in range(TRANSITION_FRAMES):
                    t = t_step / TRANSITION_FRAMES
                    interpolated = interpolate_snapshots(state, next_state, t)
                    frame = render_frame(interpolated, frame_index, total_frames)
                    frame.save(os.path.join(tmpdir, f"frame_{frame_index:06d}.png"))
                    frame_index += 1

        # 3. Stitch with FFmpeg
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", os.path.join(tmpdir, "frame_%06d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "23",
            output_path
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)

    return output_path
```

### Calculate `total_frames` before rendering

```python
total_frames = len(snapshots) * HOLD_FRAMES + (len(snapshots) - 1) * TRANSITION_FRAMES
```

---

## Position Validation Rules

All position endpoints must validate:

```python
from pydantic import validator

class PersonCreate(BaseModel):
    name: str
    x_position: float
    y_position: float
    tag_id: Optional[UUID] = None
    avatar_url: Optional[str] = None

    @validator("x_position", "y_position")
    def validate_position(cls, v):
        if not -1.0 <= v <= 1.0:
            raise ValueError("Position must be between -1.0 and 1.0")
        return round(v, 6)  # Limit precision
```

---

## CORS Configuration

Since the frontend team will be running separately:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Hackathon — allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## App Lifespan (Startup Tasks)

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # Create tables (dev mode)
    await seed_predefined_tags()  # Seed tags if they don't exist
    os.makedirs("generated/images", exist_ok=True)
    os.makedirs("generated/videos", exist_ok=True)
    yield
    # Shutdown (cleanup if needed)

app = FastAPI(title="Relationship Solar System API", lifespan=lifespan)
```

---

## Environment Variables (.env)

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/solar_system_db
APP_HOST=0.0.0.0
APP_PORT=8000
GENERATED_DIR=generated
```

---

## Testing Checklist

After implementation, verify these flows work end-to-end:

1. **Create user** → auto-creates solar system → auto-creates first snapshot
2. **Add 3 people** with different tags and positions → 3 snapshots created
3. **Move a person** closer → snapshot with "Moved X closer"
4. **Remove a person** → soft deleted, snapshot created, person gone from GET but in snapshots
5. **GET solar system** → returns only active people
6. **GET snapshots** → returns all snapshots in order
7. **Generate image** → produces a 1080x1080 PNG in `generated/images/`
8. **Generate video** → produces an MP4 in `generated/videos/` with smooth transitions
9. **Create custom tag** → usable when adding/updating people
10. **Attempt to update predefined tag** → returns 403

---

## Implementation Order (Tell Claude Code to follow this sequence)

1. **Setup:** Project structure, requirements, .env, database.py, config.py
2. **Models:** All 5 SQLAlchemy models
3. **Schemas:** All Pydantic schemas for request/response
4. **Database init:** Alembic setup OR direct `create_all` for hackathon speed
5. **Seed tags:** Predefined tags seeder
6. **Core routes:** Users, Solar System GET
7. **People CRUD:** Add, update (position + tag), soft delete — WITH snapshot creation on each
8. **Tags CRUD:** Predefined fetch, custom create/update/delete
9. **Snapshots routes:** List (paginated) and detail
10. **Image generator:** Full Strava-style Pillow implementation
11. **Video generator:** Frame rendering + interpolation + FFmpeg pipeline
12. **Static file serving:** Mount `generated/` directory
13. **Test all flows:** Use the testing checklist above

---

## Notes for Claude Code

- Use `async` everywhere — async SQLAlchemy sessions, async route handlers
- Use `selectin` loading for relationships to avoid N+1 queries
- Every person mutation (add/update/delete) MUST call `capture_snapshot()` — this is non-negotiable
- Position validation (-1.0 to 1.0) must happen at the Pydantic schema level
- The `distance_from_center` computation must happen in the service layer, NOT in the route handler
- For image generation: use Pillow's `Image.alpha_composite()` for glow effects — draw glows on a separate RGBA layer, apply GaussianBlur, then composite
- For video generation: use `tempfile.TemporaryDirectory()` for frames — clean up automatically
- Download Inter font files and place in `assets/fonts/` before running image generation
- Ensure `ffmpeg` is installed on the system for video generation
- Serve generated files via FastAPI's `StaticFiles`
- All UUIDs should be generated server-side using `uuid.uuid4()`
- Use `func.now()` for all timestamps — let the database handle time
