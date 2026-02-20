# Docker Deployment Guide

This guide covers running the Teams Chat Export application using Docker and
Docker Compose.

---

## Prerequisites

- **Docker** 20.10+ ([install](https://docs.docker.com/engine/install/))
- **Docker Compose** 2.0+ (included with Docker Desktop)
- A `.env` file with `TEAMS_CLIENT_ID` and `TEAMS_TENANT_ID`

---

## Quick Start: Docker Compose

**One command to start both services:**

```bash
docker-compose up
```

Visit **http://localhost:8080** — the app auto-detects that the API is at
`http://api:8000` (via service name resolution on the internal Docker network).

**Flags:**

| Flag | Effect |
|------|--------|
| `-d` | Run in background (detached mode) |
| `--build` | Rebuild images before starting |
| `-V` | Ignore `.env` volume mount (mount source for development) |
| `--pull=always` | Pull latest base images |

**Examples:**

```bash
# Development with hot-reload
docker-compose up --build -V

# Background production
docker-compose up -d --pull=always

# Stop services
docker-compose down

# Remove volumes and images
docker-compose down -v --rmi all

# View logs
docker-compose logs -f api web
```

---

## Docker Compose: Architecture

```yaml
extract-teams-chat (network)
├── api (service)
│   ├── Port: 8000
│   ├── Image: teams-chat-api
│   ├── Volume: .env (read-only)
│   └── Health check: GET /api/auth/status
│
└── web (service)
    ├── Port: 8080
    ├── Image: teams-chat-web
    ├── Env: API_URL=http://api:8000
    └── Health check: GET /
```

The `web` service **depends_on** the `api` service with a health check — the web
container waits for the API to be healthy before starting.

---

## Building Images Manually

**Build both images:**

```bash
docker build -f Dockerfile.api -t teams-chat-api:latest .
docker build -f Dockerfile.web -t teams-chat-web:latest .
```

**Build via Compose:**

```bash
docker-compose build
```

**Push to a registry:**

```bash
docker tag teams-chat-api:latest myregistry/teams-chat-api:latest
docker push myregistry/teams-chat-api:latest
```

---

## Running Containers Independently

### Scenario 1: Both containers on Docker network

```bash
# Create a custom network
docker network create teams-chat

# Start API
docker run \
  --name api \
  --network teams-chat \
  --env-file .env \
  -p 8000:8000 \
  teams-chat-api

# Start Web (in another terminal)
docker run \
  --name web \
  --network teams-chat \
  -e API_URL=http://api:8000 \
  -p 8080:8080 \
  teams-chat-web
```

The web container can access the API at `http://api:8000` (service name DNS resolution).

### Scenario 2: API on host, Web in Docker

```bash
# Terminal 1: Run API on the host
python -m uvicorn server:app --host 0.0.0.0 --port 8000

# Terminal 2: Run Web container
docker run \
  -e API_URL=http://host.docker.internal:8000 \
  -p 8080:8080 \
  teams-chat-web
```

`host.docker.internal` is a special DNS name that resolves to the host machine
from inside a Docker container (Docker Desktop on Windows/Mac; on Linux, use
`--network host` or `--add-host host.docker.internal:host-gateway`).

### Scenario 3: API in Docker, Web on host

```bash
# Terminal 1: Run API container
docker run \
  --env-file .env \
  -p 8000:8000 \
  teams-chat-api

# Terminal 2: Run Web locally
python -m http.server 8080 --directory web
```

The host's JavaScript will connect to `http://localhost:8000` (or override with
`window.API_BASE`).

---

## Environment Variables & Configuration

### API Container

The API container requires `.env` to be mounted:

```bash
docker run --env-file .env teams-chat-api
```

Inside the container, the Python app reads `/app/.env` via `load_env_file()`.

**Required in `.env`:**
- `TEAMS_CLIENT_ID` — Azure AD app client ID
- `TEAMS_TENANT_ID` — Azure AD tenant ID

### Web Container

The Web container builds the static HTML with the API URL injected:

```bash
docker build --build-arg API_URL=http://api:8000 -f Dockerfile.web -t teams-chat-web .
```

Or via Docker Compose (done automatically):

```yaml
web:
  build:
    args:
      API_URL: http://api:8000
```

**At runtime**, the `API_URL` environment variable is available but doesn't
override the build-time value (it's baked into the HTML). To allow runtime
override, set `window.API_BASE` in JavaScript before loading `app.js`.

---

## Debugging

### View logs

```bash
# All services
docker-compose logs

# Just API
docker-compose logs api

# Follow logs
docker-compose logs -f web
```

### Exec into a running container

```bash
# Open shell in API container
docker-compose exec api /bin/bash

# Check .env
docker-compose exec api cat /app/.env

# Test API endpoint
docker-compose exec api curl http://localhost:8000/api/auth/status
```

### Rebuild and restart

```bash
docker-compose down
docker-compose up --build
```

### Check container health

```bash
docker-compose ps
```

**Status column:**
- `Up (healthy)` — running and healthcheck passed
- `Up (starting)` — running, waiting for healthcheck
- `Exited (1)` — crashed

---

## Production Deployment

### Docker Swarm

```bash
# Build and push images
docker build -f Dockerfile.api -t myregistry/teams-chat-api:1.0 .
docker push myregistry/teams-chat-api:1.0

# Deploy stack
docker stack deploy -c docker-compose.yml teams-chat
```

### Kubernetes

Convert `docker-compose.yml` using [kompose](https://kompose.io):

```bash
kompose convert -f docker-compose.yml -o k8s/
kubectl apply -f k8s/
```

### Secrets Management

Instead of mounting `.env`, use Docker secrets:

```bash
docker secret create teams_client_id -
docker secret create teams_tenant_id -

# In docker-compose.yml
secrets:
  teams_client_id:
    external: true
  teams_tenant_id:
    external: true

services:
  api:
    secrets:
      - teams_client_id
      - teams_tenant_id
    # Inside container, files are at:
    # /run/secrets/teams_client_id
    # /run/secrets/teams_tenant_id
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Error: .env file not found` | API container can't read mounted `.env` | Ensure `docker-compose up` is run from project root |
| `Connection refused: localhost:8000` | Web container can't reach API | Use service name (`http://api:8000`) on Docker network |
| `CORS error: localhost:8080` | API CORS config issue | Check `server.py` CORS middleware |
| `API_URL=http://localhost:8000` in Docker | Localhost doesn't exist inside container | Use `http://api:8000` (service name) or `http://host.docker.internal:8000` |
| Health check fails | Service not ready | Check logs: `docker-compose logs api` |
| Port already in use | Port 8000 or 8080 in use | Change: `-p 9000:8000` or update `.ports` in `docker-compose.yml` |

---

## Advanced: Multi-Stage Builds

Both `Dockerfile.api` and `Dockerfile.web` use multi-stage builds:

1. **Builder stage** — compile/prepare dependencies
2. **Runtime stage** — minimal final image (smaller, faster, more secure)

Benefits:
- ✅ Smaller images (builder deps not included)
- ✅ Non-root user for security
- ✅ Health checks built-in
- ✅ Fast rebuilds (dependency layer caching)

---

## Network Modes

| Mode | Use case | Network | DNS |
|------|----------|---------|-----|
| Docker Compose (default) | Development & production | Private bridge | Service name resolution |
| `--network host` | Linux only; max performance | Host network | `localhost` |
| `--network custom` | Multi-container apps | Custom bridge | Service names |

---

## Additional Resources

- [Docker Docs](https://docs.docker.com/)
- [Docker Compose Docs](https://docs.docker.com/compose/)
- [Best Practices](https://docs.docker.com/develop/dev-best-practices/)
