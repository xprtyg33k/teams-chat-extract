"""
Application entry point – FastAPI server.

Serves:
  /api/*   → REST API routes
  /*       → Static files from /web  (SPA fallback)
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from api.routes import router as api_router

app = FastAPI(
    title="Teams Chat Export",
    version="2.0.0",
    description="Web UI & REST API for Microsoft Teams chat export",
)

# CORS – allow the dev server (Vite / Live Server) if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router)

# Serve static web files at root (SPA fallback)
app.mount("/", StaticFiles(directory="web", html=True), name="web")


def main() -> None:
    uvicorn.run("server:app", host="127.0.0.1", port=8080, reload=True)


if __name__ == "__main__":
    main()
