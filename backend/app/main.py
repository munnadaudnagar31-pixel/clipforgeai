import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 1. Force absolute system paths into runtime before importing local modules
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../.."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from api.auth import router as auth_router
from api.videos import router as videos_router
from api.clips import router as clips_router
from database import engine
from models import models

# Force Table Creation
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ClipForge AI API",
    description="Backend engine for automated video clipping and processing",
    version="1.0.0"
)

# 3. Configure CORS Middleware for UI interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Include Routers cleanly using explicit absolute modules
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(videos_router, prefix="/api/videos", tags=["videos"])
app.include_router(clips_router, prefix="/api/clips", tags=["clips"])

@app.get("/")
def read_root():
    return {"status": "healthy", "message": "ClipForge AI Backend Engine is running perfectly!"}
