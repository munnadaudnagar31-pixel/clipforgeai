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

# 2. Explicit Absolute Imports to kill IDE and Container errors permanently
from backend.app.api import auth, videos, clips

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
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(videos.router, prefix="/api/videos", tags=["Videos"])
app.include_router(clips.router, prefix="/api/clips", tags=["Clips"])

@app.get("/")
def read_root():
    return {"status": "healthy", "message": "ClipForge AI Backend Engine is running perfectly!"}
