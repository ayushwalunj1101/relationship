# Relationship Solar System

A FastAPI backend that visualizes your relationships as a solar system. You are the sun at the center, and the people in your life orbit around you as planets — the closer they are, the stronger the bond.

## Features

- **2D Relationship Mapping** — Place people on a normalized coordinate plane (-1.0 to 1.0). Distance from center represents emotional closeness.
- **Relationship Tags** — Categorize people as Partner, Family, Close Friend, Friend, Colleague, Mentor, Acquaintance, or create custom tags.
- **Snapshot History** — Every change (add, move, remove a person) automatically captures a full-state JSONB snapshot for timeline tracking.
- **Image Generation** — Generate Strava-style 1080x1080 shareable PNG images with radial gradients, orbital rings, glowing planets, and stats.
- **Video Generation** — Create timeline videos from snapshots with smooth interpolated transitions, stitched via FFmpeg.

## Tech Stack

- **Framework:** FastAPI (async)
- **Database:** PostgreSQL 15+ with JSONB
- **ORM:** SQLAlchemy 2.0 (async, asyncpg driver)
- **Validation:** Pydantic v2
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
│   ├── routers/             # API route handlers
│   ├── services/            # Business logic + image/video generation
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
- FFmpeg (for video generation)

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
| GET | `/api/solar-system/{user_id}` | Get full solar system state |

### People
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/solar-system/{user_id}/people/` | Add a person |
| PATCH | `/api/solar-system/{user_id}/people/{person_id}` | Update position/tag/name |
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

## Quick Test

```bash
# Create a user
curl -X POST http://localhost:8000/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Ayush", "email": "ayush@example.com"}'

# Add a person (use the user_id from above)
curl -X POST http://localhost:8000/api/solar-system/{user_id}/people/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Best Friend", "x_position": 0.2, "y_position": 0.1}'

# Generate an image
curl -X POST http://localhost:8000/api/solar-system/{user_id}/generate-image
```
