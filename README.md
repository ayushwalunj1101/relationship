# Relationship Solar System

A FastAPI backend that visualizes your relationships as a solar system. You are the sun at the center, and the people in your life orbit around you as planets — the closer they are, the stronger the bond.

## Features

- **Relationship Mapping** — Place people on a normalized coordinate plane (-1.0 to 1.0). Distance from center represents emotional closeness.
- **Animation-Ready API** — Each person has `orbit_speed`, `planet_size`, `custom_color`, `notes`, and `relationship_score` fields for frontend animation flexibility.
- **Theme Configuration** — Store any frontend visual config (background style, particle effects, glow intensity) as a JSONB blob via the theme endpoint.
- **Relationship Tags** — Categorize people as Partner, Family, Close Friend, Friend, Colleague, Mentor, Acquaintance, or create custom tags.
- **Snapshot History** — Every change automatically captures a full-state JSONB snapshot for timeline tracking.
- **Real-time Updates** — WebSocket endpoint streams live events (person added/moved/removed, theme changed) for instant UI updates.
- **Bulk Operations** — Update multiple people's positions in a single API call with one snapshot.
- **Analytics** — Computed stats: distances, tag distribution, relationship score breakdown, 30-day activity timeline.
- **Image Generation** — Generate Strava-style 1080x1080 shareable PNG images.
- **Video Generation** — Create timeline videos from snapshots with smooth interpolated transitions via FFmpeg.

## Tech Stack

- **Framework:** FastAPI (async)
- **Database:** PostgreSQL 15+ with JSONB
- **ORM:** SQLAlchemy 2.0 (async, asyncpg driver)
- **Validation:** Pydantic v2
- **Real-time:** WebSocket (built-in via uvicorn)
- **Image Generation:** Pillow (PIL)
- **Video Generation:** Pillow + FFmpeg
- **Server:** Uvicorn

## Project Structure

```
solar-system-api/
├── app/
│   ├── main.py              # FastAPI app, lifespan, CORS, routers
│   ├── config.py            # Settings via pydantic-settings
│   ├── database.py          # Async engine, sessionmaker, get_db
│   ├── models/              # SQLAlchemy models (User, SolarSystem, Person, Tag, Snapshot)
│   ├── schemas/             # Pydantic request/response schemas
│   ├── routers/             # API route handlers + WebSocket
│   ├── services/            # Business logic, stats, image/video generation, WebSocket manager
│   └── utils/               # Tag seeder, interpolation helpers
├── assets/fonts/            # Inter font files for image rendering
├── migrations/              # Alembic migrations
├── requirements.txt
└── .env                     # Environment config (not committed)
```

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- FFmpeg (optional, for video generation)

### Installation

```bash
cd solar-system-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Database Setup

1. Create a PostgreSQL database:
   ```bash
   createdb -U postgres solar_system_db
   ```

2. Create a `.env` file in `solar-system-api/`:
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/solar_system_db
   APP_HOST=0.0.0.0
   APP_PORT=8000
   GENERATED_DIR=generated
   ```

3. Tables are auto-created on startup via `Base.metadata.create_all`.

### Run the Server

```bash
cd solar-system-api
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000/docs** for the Swagger UI.

## API Endpoints

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/users/` | Create user (auto-creates solar system) |
| GET | `/api/users/{user_id}` | Get user details |

### Solar System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/solar-system/{user_id}` | Get full state (people, tags, theme, stats, last_activity) |
| PATCH | `/api/solar-system/{user_id}/theme` | Update frontend theme config |
| GET | `/api/solar-system/{user_id}/stats` | Get computed analytics |

### People
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/solar-system/{user_id}/people/` | Add a person |
| PATCH | `/api/solar-system/{user_id}/people/bulk` | Bulk update positions |
| PATCH | `/api/solar-system/{user_id}/people/{person_id}` | Update a person |
| DELETE | `/api/solar-system/{user_id}/people/{person_id}` | Remove a person (soft delete) |

### Tags
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tags/predefined` | List predefined tags |
| POST | `/api/solar-system/{user_id}/tags` | Create custom tag |
| PATCH | `/api/solar-system/{user_id}/tags/{tag_id}` | Update custom tag |
| DELETE | `/api/solar-system/{user_id}/tags/{tag_id}` | Delete custom tag |

### Snapshots
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/solar-system/{user_id}/snapshots/` | Paginated snapshot list |
| GET | `/api/solar-system/{user_id}/snapshots/{snapshot_id}` | Snapshot detail with full state |

### Generation
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/solar-system/{user_id}/generate-image` | Generate shareable PNG |
| POST | `/api/solar-system/{user_id}/generate-video` | Generate timeline video (MP4) |

### WebSocket
| Method | Endpoint | Description |
|--------|----------|-------------|
| WS | `/api/solar-system/{user_id}/ws` | Real-time event stream |

**WebSocket events:** `person_added`, `person_removed`, `person_moved`, `person_tag_changed`, `bulk_update`, `theme_updated`

## Person Fields

Each person (planet) supports these fields for frontend animation:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | required | Person's name |
| `x_position` | float | required | X coordinate (-1.0 to 1.0) |
| `y_position` | float | required | Y coordinate (-1.0 to 1.0) |
| `tag_id` | UUID | null | Relationship tag |
| `orbit_speed` | float | 1.0 | Animation speed multiplier |
| `planet_size` | float | 1.0 | Visual size multiplier |
| `custom_color` | string | null | Hex color override (e.g. `#FF5733`) |
| `notes` | string | null | Description / hover text |
| `relationship_score` | int | null | 0-100 closeness metric |

## Quick Test

```bash
# Create a user
curl -X POST http://localhost:8000/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Ayush", "email": "ayush@example.com"}'

# Add a person with animation fields (use the user_id from above)
curl -X POST http://localhost:8000/api/solar-system/{user_id}/people/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Best Friend", "x_position": 0.2, "y_position": 0.1, "orbit_speed": 1.5, "planet_size": 1.2, "custom_color": "#FF5733", "relationship_score": 95}'

# Set a theme
curl -X PATCH http://localhost:8000/api/solar-system/{user_id}/theme \
  -H "Content-Type: application/json" \
  -d '{"theme": {"background": "cosmic", "animation_speed": 1.2, "show_orbits": true}}'

# Get stats
curl http://localhost:8000/api/solar-system/{user_id}/stats

# Generate an image
curl -X POST http://localhost:8000/api/solar-system/{user_id}/generate-image
```
