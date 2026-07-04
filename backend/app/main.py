import os
import sys
# Inject workspace paths to fix IDE red lines and Render imports
_app_dir = os.path.dirname(os.path.abspath(__file__))
while os.path.basename(_app_dir) != 'app' and _app_dir != os.path.dirname(_app_dir):
    _app_dir = os.path.dirname(_app_dir)
_backend_dir = os.path.dirname(_app_dir)
_root_dir = os.path.dirname(_backend_dir)
if _backend_dir not in sys.path: sys.path.insert(0, _backend_dir)
if _root_dir not in sys.path: sys.path.insert(0, _root_dir)
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
ClipForge AI â€” FastAPI Backend Entry Point

Run locally:
  cd backend
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

API docs:
  http://localhost:8000/api/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import engine, Base

# Optional Sentry
if settings.SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.2)


# â”€â”€ Lifespan: auto-create tables on startup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import all models so their metadata is registered
    from .models import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("âœ… Database tables verified/created.")
    yield
    await engine.dispose()


# â”€â”€ App â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app = FastAPI(
    title="ClipForge AI API",
    description="AI-powered gaming highlight clip generator backend",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# â”€â”€ CORS â€” allow frontend (file:// opens send origin as 'null') â”€â”€â”€
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# â”€â”€ Global exception handler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# â”€â”€ Routers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from .api import auth, videos, clips   # noqa: E402

app.include_router(auth.router,   prefix="/api/auth",   tags=["Auth"])
app.include_router(videos.router, prefix="/api/videos", tags=["Videos"])
app.include_router(clips.router,  prefix="/api/clips",  tags=["Clips"])

# Optional: export, webhooks (may import heavy optional deps)
try:
    from .api import export, webhooks
    app.include_router(export.router,   prefix="/api/export",   tags=["Export"])
    app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
except Exception as e:
    print(f"[Startup] Optional routers not loaded: {e}")


# â”€â”€ Health â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.get("/api/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": "1.0.0", "service": "ClipForge AI"}

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

@app.get("/{page}.html", tags=["Frontend"])
async def serve_html(page: str):
    file_path = os.path.join(frontend_path, f"{page}.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return JSONResponse(status_code=404, content={"error": "Page not found"})

@app.get("/favicon.svg", tags=["Frontend"])
async def serve_favicon():
    return FileResponse(os.path.join(frontend_path, "favicon.svg"))

@app.get("/manifest.json", tags=["Frontend"])
async def serve_manifest():
    return FileResponse(os.path.join(frontend_path, "manifest.json"))

@app.get("/", tags=["Frontend"])
async def root():
    return FileResponse(os.path.join(frontend_path, "index.html"))

# Mount frontend directories securely
for folder in ["scripts", "styles", "assets"]:
    folder_path = os.path.join(frontend_path, folder)
    if os.path.exists(folder_path):
        app.mount(f"/{folder}", StaticFiles(directory=folder_path), name=folder)


