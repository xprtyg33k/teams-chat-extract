# Project Summary: Teams Chat Export

## Overview

A full-stack tool for exporting Microsoft Teams chat messages.  The primary
interface is a browser-based Web UI backed by a FastAPI REST server.  A set
of CLI scripts is also available for headless/scripted use.

**Current Version:** 2.0.0
**Last Updated:** February 20, 2026

## Architecture

```
Browser (SPA)
    └── business.js (orchestration layer)
            └── api.js (HTTP client)
                    └── FastAPI /api/* (server.py)
                            ├── auth_manager.py   (MSAL device-code flow)
                            ├── run_manager.py    (background threads)
                            └── cli/teams_chat_export.py  (Graph API client)
```

## Capabilities


### Core Features

| Feature | Status | Details |
|---------|--------|---------|
| Web UI | ✅ Complete | Dark-themed SPA at `/`, served by FastAPI |
| REST API | ✅ Complete | `GET`/`POST` endpoints under `/api` |
| Background job execution | ✅ Complete | Threaded, polled via `run_id` token |
| Real-time progress bar | ✅ Complete | 0–100% with message updates |
| Results grid | ✅ Complete | Sortable, searchable, paginated, copy-to-clipboard |
| File download | ✅ Complete | Served by `/api/runs/{id}/download` |
| Run history | ✅ Complete | localStorage DB, merged with server state |
| Export chat messages | ✅ Complete | Date range, JSON/TXT format, system-message filter |
| List chats | ✅ Complete | Filter by type, topic, participant count |
| Active chats | ✅ Complete | Sorted by last activity date |
| Device-code auth | ✅ Complete | MSAL flow, token cached to `.token_cache.bin` |
| CLI scripts | ✅ Complete | Independent of web server, same Graph client |
| Unit tests (67) | ✅ Complete | pytest, 100% passing |

### Modules

**API (`api/`)**

| Module | Responsibility |
|--------|---------------|
| `routes.py` | FastAPI router — all `/api/*` endpoints |
| `auth_manager.py` | MSAL device-code flow, token cache, session validation |
| `run_manager.py` | Thread pool, job state store, result files |
| `models.py` | Pydantic schemas for all requests and responses |

**Web (`web/js/`)**

| Module | Responsibility |
|--------|---------------|
| `api.js` | Thin `fetch` wrappers for every API endpoint |
| `storage.js` | localStorage persistence (auth info + run history DB) |
| `business.js` | Orchestration, event bus, polling lifecycle |
| `ui.js` | All DOM reads/writes — forms, grid, progress, history |
| `app.js` | Bootstrap — wires business events to UI, binds listeners |

**CLI (`cli/`)**

| Script | Responsibility |
|--------|---------------|
| `teams_chat_export.py` | Core Graph client, export logic, auth utilities |
| `list_chats.py` | Chat discovery with filtering |
| `list_active_chats.py` | Activity-sorted chat list |

## Configuration

### Required Settings

```
TEAMS_CLIENT_ID: Azure AD application ID
TEAMS_TENANT_ID: Azure AD tenant ID
```

### Configuration Methods (in priority order)

1. `.env` file in project root (mounted read-only in Docker)
2. Windows environment variables
3. Command-line arguments

### Example `.env`

```
TEAMS_CLIENT_ID=0e2ae6dc-ea8b-40b0-8001-61e902fe42a0
TEAMS_TENANT_ID=5a8e2b45-25f8-40ea-a914-b466436e9417
```

### Docker Deployment

For Docker/Compose deployment, create `.env` in project root. The file is mounted as a read-only volume:

```bash
# Start both API and Web UI
docker-compose up

# With auto-rebuild
docker-compose up --build

# Run in background
docker-compose up -d
```

See **[docs/DOCKER.md](docs/DOCKER.md)** for comprehensive deployment options.

## Command Reference

### Export Chat

```bash
# Basic export
python -m cli.teams_chat_export --chat-id "chatid@thread.v2" --since 2025-01-01

# With end date
python -m cli.teams_chat_export --chat-id "chatid@thread.v2" --since 2025-01-01 --until 2025-12-31

# Exclude system messages
python -m cli.teams_chat_export --chat-id "chatid@thread.v2" --since 2025-01-01 --exclude-system-messages

# Plain-text output
python -m cli.teams_chat_export --chat-id "chatid@thread.v2" --since 2025-01-01 --format txt

# Force re-authentication
python -m cli.teams_chat_export --chat-id "chatid@thread.v2" --since 2025-01-01 --force-login
```

### Discover Chats

```bash
# List all chats
python -m cli.list_chats

# Filter by type and topic
python -m cli.list_chats --chat-type group --topic-include project
```

### Find Active Chats

```bash
# Active in last 365 days (default)
python -m cli.list_active_chats

# Tighter window
python -m cli.list_active_chats --min-activity-days 90
```



## Documentation

| File | Purpose |
|------|---------|  
| `README.md` | Full architecture, setup, API overview, deployment options |
| `QUICKSTART.md` | 5-minute Web UI getting-started guide (local or Docker) |
| `PROJECT_SUMMARY.md` | This file — feature overview and module reference |
| `cli/QUICKSTART.md` | CLI-specific quick start |
| `docs/DOCKER.md` | Docker/Compose deployment guide with networking and troubleshooting |
| `docs/` | Planning docs, investigation reports, daily logs |## Recent Updates (v2.0.0 — February 20, 2026)

✅ FastAPI REST server (`server.py`)
✅ Full Web UI — dark-themed SPA with auth gate, forms, progress, grid, history
✅ Background job execution with `run_id` polling tokens
✅ File download via API (results no longer written to `/out`)
✅ localStorage run history DB with server-state merge
✅ `api/` layer — clean separation of auth, run management, and routing
✅ `web/js/` — layered frontend: api → storage → business → ui → app
✅ All 67 existing unit tests continue to pass
✅ **Docker containerization** — multi-stage builds, service networking, health checks
✅ **Docker Compose orchestration** — one-command deployment with automatic API_URL injection

## Known Limitations

- File attachments are not exported (text content only)
- Run history is in-memory server-side (resets on server restart); local history persists in browser
- Token cache is machine-local (`.token_cache.bin`)
- System messages are included in exports by default; use the checkbox/flag to exclude them

## Requirements

See `requirements.txt` for all Python dependencies.

Key packages:
- `fastapi` + `uvicorn` — web server
- `msal` — Microsoft Authentication Library
- `requests` — HTTP client for Graph API
- `pydantic` — data validation
- `html2text` / `beautifulsoup4` — HTML to plain-text conversion


