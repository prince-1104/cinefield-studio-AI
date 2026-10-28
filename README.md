# 🎬 AI Ad Film Studio

An AI-powered cinematic advertising platform that generates professional video advertisements from a product brief.

## Features (MVP)

1. **Product Brief** — Enter product name, audience, tone, and call-to-action
2. **Storyboard Generation** — AI generates a structured script with 3 storyboard shots
3. **Approval Workflow** — Review and approve the storyboard before production
4. **Video Generation** — Generate 3 real video clips using Gemini Omni Flash
5. **Narration** — AI-generated text-to-speech narration
6. **Assembly** — Clips, narration, music, captions, logo, and CTA composed into a final MP4
7. **Progress Tracking** — Real-time progress via SSE, per-shot retry, final download

## Architecture

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite |
| API | Python, FastAPI |
| Database | PostgreSQL 16, SQLAlchemy 2, Alembic |
| Worker | Separate Python process, DB-backed job queue |
| Video AI | Google Gemini Omni Flash (`gemini-omni-1.1-flash`) via Interactions API |
| Text AI | Google Gemini (`gemini-3.5-flash`, configurable) |
| Speech | OpenAI TTS (`gpt-4o-mini-tts`, configurable) |
| Renderer | FFmpeg behind a `MediaRenderer` interface |
| Storage | Local filesystem behind an `ArtifactStorage` interface |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- API keys for Google Gemini and OpenAI (optional for scaffold testing)

### Setup

```bash
# Clone and enter the project
cd pexyl.ai

# Copy environment file and add your API keys
cp .env.example .env
# Edit .env with your GEMINI_API_KEY and OPENAI_API_KEY

# Start all services
docker compose up --build

# Services:
#   Frontend  → http://localhost:5173
#   API       → http://localhost:8000/api/docs
#   Postgres  → localhost:5432
```

### Verify

```bash
# Health check
curl http://localhost:8000/api/health

# Expected: {"status":"ok","service":"ad-film-studio-api"}
```

## Project Structure

```
pexyl.ai/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/              # Database migrations
│   ├── app/
│   │   ├── main.py           # FastAPI application
│   │   ├── config.py         # Pydantic Settings
│   │   ├── database.py       # SQLAlchemy async engine
│   │   ├── models/           # ORM models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── routers/          # API endpoints
│   │   ├── services/         # Business logic
│   │   └── interfaces/       # Provider ABCs
│   └── worker/
│       └── runner.py         # Background job processor
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── main.tsx
        └── App.tsx
```

## Configuration

All settings are environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://…` | PostgreSQL connection string |
| `GEMINI_API_KEY` | — | Google AI API key |
| `GEMINI_TEXT_MODEL` | `gemini-3.5-flash` | Model for script/storyboard planning |
| `GEMINI_VIDEO_MODEL` | `gemini-omni-1.1-flash` | Model for video generation |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `OPENAI_TTS_MODEL` | `gpt-4o-mini-tts` | Text-to-speech model |
| `OPENAI_TTS_VOICE` | `coral` | TTS voice selection |
| `ARTIFACT_DIR` | `/data/artifacts` | Path for generated media files |

## License

Proprietary — Pexyl AI
