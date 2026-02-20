# Quick Start — Web UI & API

Get the Teams Chat Export web interface running in under five minutes.

## Prerequisites

- **Docker + Docker Compose** (easiest) OR Python 3.9+
- A Microsoft Teams account
- A `TEAMS_TENANT_ID` and `TEAMS_CLIENT_ID` — see step 1 below

---

## 1. Get your Azure AD credentials

You need two values: a **Tenant ID** (identifies your organization) and a
**Client ID** (identifies the app registration).  These are **not secrets** —
they are safe to share with anyone in the same Azure AD tenant.

> **Already have them?** If a coworker or admin has already registered the app,
> ask them for the two IDs and skip straight to
> [step 2 — Configure credentials](#2-configure-credentials).

### First-time setup (one-time per organization)

Only one person in your organization needs to do this.  Once complete, share the
two IDs with your team — every user authenticates individually with their own
Microsoft account.

1. Go to **Azure Portal → App registrations → New registration**
2. Name it (e.g. `TeamsExport`), choose **Single tenant**, click **Register**
3. Note the **Application (client) ID** and **Directory (tenant) ID**
4. Under **API permissions → Add permission → Microsoft Graph → Delegated**:
   - `Chat.Read`
   - `User.ReadBasic.All`
5. Click **Grant admin consent** (or ask your tenant admin)

---

## 2. Configure credentials

Create a `.env` file in the project root:

```
TEAMS_CLIENT_ID=<application-client-id>
TEAMS_TENANT_ID=<tenant-id>
```

---

## 3. Start the server

### Option A: Docker Compose (Recommended)

```bash
docker-compose up
```

Visit **http://localhost:8080** — both API and Web UI start automatically.

### Option B: Local Python

Install dependencies:

```powershell
pip install -r requirements.txt
```

Start the server:

```powershell
python -m uvicorn server:app --host 127.0.0.1 --port 8080
```

Navigate to **[http://127.0.0.1:8080](http://127.0.0.1:8080)** in your browser.

---

## 4. Sign in

The app checks for a cached token automatically.

- **If already signed in** — your name appears in the top-right badge and the
  main panel is immediately available.
- **If not signed in** — click **Start Login**.  A device code will appear.
  Open [https://microsoft.com/devicelogin](https://microsoft.com/devicelogin),
  enter the code, and sign in with your Microsoft account.  The app detects
  completion and unlocks automatically.

---

## 5. Run an action

Select one of the three actions from the left sidebar:

| Action | What it does |
|--------|-------------|
| **Export Chat** | Downloads all messages from a specific chat for a date range |
| **List Chats** | Browses and filters your chats by type, topic, or participant |
| **Active Chats** | Finds chats with recent activity, sorted by last message date |

Fill in the form and click the action button.  A progress bar tracks the
background job in real time.

---

## 6. View and download results

When the job completes:

- **Summary cards** show totals, date range, top senders, etc.
- **Interactive grid** displays the top 50 rows — sortable by column, full-text
  searchable, paginated, and copyable to clipboard (TSV format).
- **⬇ Download** saves the full result file (JSON) to your computer.

---

## 7. Run history

Click **Run History** in the sidebar to see all previous runs.  Each entry
shows the action type, time, and status.  Completed runs have a download
button.  History persists in your browser's local storage.

---

## API reference

The interactive API docs are at **[http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs)** (Swagger UI).

Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/auth/status` | Check if a valid token is cached |
| `POST` | `/api/auth/device-code` | Start device-code login flow |
| `POST` | `/api/auth/device-code/poll` | Poll for login completion |
| `POST` | `/api/runs/list-chats` | Start a List Chats job |
| `POST` | `/api/runs/list-active-chats` | Start an Active Chats job |
| `POST` | `/api/runs/export-chat` | Start a Chat Export job |
| `GET` | `/api/runs/{run_id}/status` | Poll job progress |
| `GET` | `/api/runs/{run_id}/results` | Get grid-ready results |
| `GET` | `/api/runs/{run_id}/download` | Download result file |
| `GET` | `/api/runs/history` | List all past runs |

---

## CLI alternative

Prefer the terminal?  See [cli/QUICKSTART.md](cli/QUICKSTART.md) for direct
script usage without the web server.

---

## 8. Troubleshooting

| Symptom | Fix |
|---------|-----|
| Login button does nothing / error | Check `.env` has `TEAMS_CLIENT_ID` and `TEAMS_TENANT_ID` |
| Device code expires | Click **Start Login** again to get a fresh code |
| Run fails immediately | Open `/docs`, hit `GET /api/auth/status` to confirm authentication |
| Port 8080 in use | Change port: `--port 9000` or `docker-compose up -e WEB_PORT=9090` |
| `Chat.Read` permission error | Verify admin consent is granted in Azure Portal |

---

## More deployment options

See [README.md](README.md) for:
- Individual Docker container runs
- Mixed local API + Docker web
- Production Compose configurations
- Full troubleshooting guide

For detailed Docker deployment including health checks, networking, and volume management,
see [docs/DOCKER.md](docs/DOCKER.md).

For CLI-only usage (no web server), see [cli/QUICKSTART.md](cli/QUICKSTART.md).

