# Teams Chat Export

Export Microsoft Teams chat messages through a modern browser-based interface
or directly from the command line.

## Overview

| Mode | Entry point | Best for |
|------|-------------|----------|
| **Web UI + API** | `server.py` (FastAPI) | Interactive use, downloads, history |
| **CLI scripts** | `cli/` | Automation, scripting, headless servers |

Both modes share the same underlying Microsoft Graph API client and
authentication logic.

---

## Features

- 🔐 **Device-code authentication** — sign in via browser, token cached locally
- 📤 **Export chat messages** — full date-range filtering, JSON or TXT output
- 📝 **Export meeting transcripts** — download meeting transcripts as TXT or JSON
- 📋 **List chats** — filter by type, topic, participant count
- 🟢 **Active chats** — find recently active chats sorted by last message
- 📊 **Interactive results grid** — sortable, searchable, paginated, copy-to-clipboard
- ⬇ **Download results** — file served directly to the browser, nothing written to `/out`
- 🕘 **Run history** — persisted in browser local storage, survives page reloads
- ⚡ **Background jobs** — runs execute in threads; real-time progress bar

---

## Project Structure

```
extract-teams-chat/
├── server.py               # FastAPI entry point (serves API + static web files)
├── requirements.txt        # Python dependencies
├── .env                    # Credentials (git-ignored)
│
├── api/                    # REST API layer
│   ├── routes.py           # All /api/* endpoints
│   ├── auth_manager.py     # Token lifecycle (MSAL device-code flow)
│   ├── run_manager.py      # Background job execution & result storage
│   └── models.py           # Pydantic request/response schemas
│
├── web/                    # Single-page frontend (dark themed)
│   ├── index.html
│   ├── css/styles.css
│   └── js/
│       ├── api.js          # HTTP client (thin fetch wrappers)
│       ├── storage.js      # localStorage persistence layer
│       ├── business.js     # Orchestration & event bus
│       ├── ui.js           # All DOM manipulation
│       └── app.js          # Entry point — wires events to UI
│
├── cli/                    # Command-line scripts
│   ├── teams_chat_export.py
│   ├── list_chats.py
│   ├── list_active_chats.py
│   └── QUICKSTART.md       # CLI-specific quick start
│
├── tests/                  # pytest unit tests
│
└── docs/                   # Planning, investigation & daily logs
    ├── INVESTIGATION_REPORT.md
    ├── PLANNED_IMPROVEMENTS.md
    ├── PROJECT_EVALUATION_AND_IMPROVEMENTS_2025-12-10_20H.md
    └── dailies/
```

---

## Quick Start

See **[QUICKSTART.md](QUICKSTART.md)** for the 5-minute Web UI setup.

For CLI-only usage see **[cli/QUICKSTART.md](cli/QUICKSTART.md)**.

---

## Azure AD Credentials

This tool requires two identifiers to connect to Microsoft Graph:

| Variable | What it is | Scope |
|----------|-----------|-------|
| `TEAMS_TENANT_ID` | Your Azure AD **Directory (tenant) ID** — identifies your organization | One per organization |
| `TEAMS_CLIENT_ID` | The **Application (client) ID** of the registered app | One per organization |

> **These IDs are not secrets.** They identify your organization and the app
> registration, not any individual user.  They are safe to share with coworkers
> in the same Azure AD tenant.  Each person authenticates independently using
> the device-code flow and receives their own session token — they will only
> see chats their own account has access to.

### Already have the IDs?

If a coworker or admin has already set up the app registration, just ask them
for the two IDs and skip ahead to [Configure credentials](#configure-credentials).

### First-time setup (admin / one-time per organization)

> Only required if no one in your organization has registered the app yet.

1. Go to [Azure Portal](https://portal.azure.com) → **App registrations → New registration**
2. Name it (e.g. `TeamsExport`), choose **Single tenant**, click **Register**
3. Copy the **Application (client) ID** and **Directory (tenant) ID**
4. Under **API permissions → Add permission → Microsoft Graph → Delegated**:
   - `Chat.Read`
   - `User.ReadBasic.All`
   - `OnlineMeetings.Read`
   - `OnlineMeetingTranscript.Read.All`
5. Click **Grant admin consent** (or ask your tenant admin)
6. Share the two IDs with your team — anyone in the same Azure AD tenant can
   use them

### Configure credentials

Create `.env` in the project root:

```
TEAMS_CLIENT_ID=<application-client-id>
TEAMS_TENANT_ID=<tenant-id>
```

---

## Running the Web Server

### Option A: Docker Compose (Recommended)

Everything in one command:

```bash
docker-compose up
```

This starts both the API (port 8000) and Web UI (port 8080) in containers with
automatic service discovery. Visit **http://localhost:8080**.

**Development mode** (hot-reload):
```bash
docker-compose up --build -V
```

The `-V` flag ignores volume overrides from your `.env` and mounts source directories
for live editing.

### Option B: Docker (Individual Containers)

Run API and Web UI independently with explicit networking:

```bash
# Terminal 1: API container
docker run --env-file .env -p 8000:8000 teams-chat-api

# Terminal 2: Web container (must know API location)
docker run -e API_URL=http://host.docker.internal:8000 -p 8080:8080 teams-chat-web
```

On Linux, use `--network host` and `http://localhost:8000` instead.

### Option C: Local Python (No Docker)

For development without Docker:

```bash
# Terminal 1: API
python -m uvicorn server:app --host 127.0.0.1 --port 8000

# Terminal 2: Web (in another terminal)
python -m http.server 8080 --directory web
```

Then open **http://localhost:8080**.

### Option D: Python + Docker Web

Run API locally, Web in Docker:

```bash
# Terminal 1: Local API
python -m uvicorn server:app --host 0.0.0.0 --port 8000

# Terminal 2: Docker Web
docker run -e API_URL=http://host.docker.internal:8000 -p 8080:8080 teams-chat-web
```

---

## Building Docker Images

**Manually build images:**

```bash
docker build -f Dockerfile.api -t teams-chat-api .
docker build -f Dockerfile.web -t teams-chat-web .
```

**With docker-compose:**

```bash
docker-compose build
```

---

## API Overview


All endpoints are under `/api`.  Every job (run) returns a `run_id` token
used to poll status and eventually download the result file.

```
GET  /api/auth/status                 → authentication state
POST /api/auth/device-code            → start login flow
POST /api/auth/device-code/poll       → poll for completion
POST /api/auth/force-login            → clear cache, restart flow
POST /api/auth/logout                 → sign out

POST /api/runs/export-chat            → start export job
POST /api/runs/export-meeting-transcript → start transcript export job
POST /api/runs/list-chats             → start list-chats job
POST /api/runs/list-active-chats      → start active-chats job
GET  /api/runs/{run_id}/status        → poll job progress (0-100%)
GET  /api/runs/{run_id}/results       → grid-ready summary + top-50 rows
GET  /api/runs/{run_id}/download      → stream result file to browser
GET  /api/runs/history                → all past runs
```

---

## CLI Usage

> Requires the venv to be active and `.env` to be configured.

```powershell
# List chats
python -m cli.list_chats

# Find active chats
python -m cli.list_active_chats --min-activity-days 90

# Export a chat
python -m cli.teams_chat_export `
  --chat-id "19:xxxxxxxx@thread.v2" `
  --since 2025-01-01 `
  --format json
```

See [cli/QUICKSTART.md](cli/QUICKSTART.md) for the full option reference.

---

## Running Tests

```powershell
python -m pytest tests/ -v
```

Coverage report:

```powershell
python -m pytest tests/ --cov=cli --cov-report=term-missing
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `.env` variables not found | Confirm the file is in the project root (same directory as `server.py`) |
| Port 8080 already in use | Use `--port 9000` (or any free port) |
| Device code expires | Click **Start Login** again for a fresh code |
| `Chat.Read` permission error | Check admin consent in Azure Portal |
| Blank messages in TXT export | Use `--exclude-system-messages` (CLI) or the checkbox in the Web UI |
| Run fails with "Not authenticated" | Reload the page; the app will re-check token state |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | REST API framework |
| `uvicorn` | ASGI server |
| `msal` | Microsoft Authentication Library |
| `requests` | HTTP client for Graph API |
| `html2text` / `beautifulsoup4` | HTML → plain text conversion |
| `pydantic` | Request/response validation |


