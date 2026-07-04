"""
ClipForge AI — FastAPI Backend Entry Point

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

from app.config import settings
from app.database import engine, Base

# Optional Sentry
if settings.SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.2)


# ── Lifespan: auto-create tables on startup ───────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import all models so their metadata is registered
    from app.models import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables verified/created.")
    yield
    await engine.dispose()


# ── App ───────────────────────────────────────────────────────────
app = FastAPI(
    title="ClipForge AI API",
    description="AI-powered gaming highlight clip generator backend",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── CORS — allow frontend (file:// opens send origin as 'null') ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handler ──────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# ── Routers ───────────────────────────────────────────────────────
from app.api import auth, videos, clips   # noqa: E402

app.include_router(auth.router,   prefix="/api/auth",   tags=["Auth"])
app.include_router(videos.router, prefix="/api/videos", tags=["Videos"])
app.include_router(clips.router,  prefix="/api/clips",  tags=["Clips"])

# Optional: export, webhooks (may import heavy optional deps)
try:
    from app.api import export, webhooks
    app.include_router(export.router,   prefix="/api/export",   tags=["Export"])
    app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
except Exception as e:
    print(f"[Startup] Optional routers not loaded: {e}")


# ── Health ────────────────────────────────────────────────────────
@app.get("/api/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": "1.0.0", "service": "ClipForge AI"}


@app.get("/")
async def root():
    return {"message": "ClipForge AI API v1.0 — see /api/docs"}
