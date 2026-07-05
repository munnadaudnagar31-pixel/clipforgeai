"""ClipForge AI â€” Videos API Routes

Supports two modes:
  â€¢ Dev mode  (no Redis/Celery): runs pipeline as a FastAPI BackgroundTask
  â€¢ Prod mode (Redis available): queues to Celery worker

POST /api/videos/ingest-url   â€” submit a YouTube/Twitch URL
POST /api/videos/upload       â€” upload a local MP4 file
GET  /api/videos/             â€” list user's videos
GET  /api/videos/{id}/status  â€” poll processing status + clips
DELETE /api/videos/{id}       â€” delete video + clips
"""
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
import uuid
import aiofiles
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models.models import User, Video, Clip
from backend.app.api.auth import get_current_user

router = APIRouter()


# â”€â”€ Plan limits â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
PLAN_CLIP_LIMITS = {"free": 3, "pro": 30, "creator": 9999, "agency": 9999}


# â”€â”€ Schemas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class IngestUrlRequest(BaseModel):
    url:           str
    game:          str = "BGMI"
    max_clips:     int = 5
    clip_duration: int = 30
    quality:       str = "1080p"
    aspect:        str = "9:16"
    watermark:     bool = True


class VideoStatusResponse(BaseModel):
    video_id:    str
    status:      str
    clips_count: int
    clips:       List[dict]
    error_msg:   Optional[str] = None


# â”€â”€ Background pipeline runner â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async def _run_pipeline_bg(
    video_id: str,
    source_url: Optional[str],
    local_path: Optional[str],
    game: str,
    max_clips: int,
    clip_duration: int,
    watermark: bool,
):
    """
    Runs the AI pipeline as a FastAPI background task.
    Opens its own DB session so it's independent of the request session.
    """
    from backend.app.database import AsyncSessionLocal
    from backend.app.ai.pipeline import run_pipeline

    async with AsyncSessionLocal() as session:
        try:
            result = await run_pipeline(
                video_id=video_id,
                source_url=source_url,
                local_path=local_path,
                game=game,
                max_clips=max_clips,
                clip_duration=clip_duration,
                watermark=watermark,
                db_session=session,
            )
            if not result.success:
                print(f"[VideosBG] Pipeline failed for {video_id}: {result.error}")
        except Exception as e:
            print(f"[VideosBG] Unhandled exception for {video_id}: {e}")
            from sqlalchemy import update as sa_update
            try:
                await session.execute(
                    sa_update(Video)
                    .where(Video.id == video_id)
                    .values(status="failed", error_msg=str(e))
                )
                await session.commit()
            except Exception:
                pass


# â”€â”€ Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/ingest-url", status_code=202)
async def ingest_url(
    payload: IngestUrlRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a YouTube/Twitch URL and start AI processing.
    Returns immediately with video_id; use /status to poll progress.
    """
    limit = PLAN_CLIP_LIMITS.get(current_user.plan, 3)
    if current_user.clips_used_this_month >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly clip limit ({limit}) reached. Please upgrade your plan."
        )

    # Detect source type
    url = payload.url.strip()
    if "youtube.com" in url or "youtu.be" in url:
        source = "youtube"
    elif "twitch.tv" in url:
        source = "twitch"
    else:
        source = "direct"

    # Create DB record
    video = Video(
        user_id=str(current_user.id),
        title=f"{payload.game} Stream â€” {source.capitalize()} Import",
        source_url=url,
        game=payload.game,
        source=source,
        status="queued",
    )
    db.add(video)
    await db.flush()
    video_id = str(video.id)

    # Try Celery first, fall back to BackgroundTask
    queued_to_celery = False
    try:
        if settings.REDIS_URL and settings.REDIS_URL != "redis://localhost:6379/0":
            raise ImportError("Redis not configured for dev")
        from backend.app.workers.job_worker import process_video_task
        task = process_video_task.delay(
            video_id=video_id,
            source_url=url,
            s3_raw_key=None,
            game=payload.game,
            max_clips=payload.max_clips,
            clip_duration=payload.clip_duration,
            quality=payload.quality,
            aspect=payload.aspect,
            watermark=payload.watermark,
            add_music=False,
            user_plan=current_user.plan,
        )
        video.job_id = task.id
        queued_to_celery = True
    except Exception:
        pass

    if not queued_to_celery:
        # Dev mode: run in FastAPI background thread
        background_tasks.add_task(
            _run_pipeline_bg,
            video_id=video_id,
            source_url=url,
            local_path=None,
            game=payload.game,
            max_clips=payload.max_clips,
            clip_duration=payload.clip_duration,
            watermark=payload.watermark,
        )

    return {
        "video_id": video_id,
        "status":   "queued",
        "mode":     "celery" if queued_to_celery else "background",
        "message":  "Processing started. Poll /api/videos/{video_id}/status for progress.",
    }


@router.post("/upload", status_code=202)
async def upload_video(
    game:          str  = Form("BGMI"),
    max_clips:     int  = Form(5),
    clip_duration: int  = Form(30),
    quality:       str  = Form("1080p"),
    aspect:        str  = Form("9:16"),
    watermark:     bool = Form(True),
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload an MP4 file (max 2GB) and start AI processing."""
    limit = PLAN_CLIP_LIMITS.get(current_user.plan, 3)
    if current_user.clips_used_this_month >= limit:
        raise HTTPException(429, "Monthly clip limit reached.")

    # Save upload locally
    raw_dir = Path(settings.LOCAL_STORAGE_DIR) / "raw" / str(current_user.id)
    raw_dir.mkdir(parents=True, exist_ok=True)
    local_filename = f"{uuid.uuid4()}.mp4"
    local_path = str(raw_dir / local_filename)

    async with aiofiles.open(local_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    file_size = os.path.getsize(local_path)

    video = Video(
        user_id=str(current_user.id),
        title=file.filename or "Uploaded Video",
        game=game,
        source="upload",
        status="queued",
        file_size_bytes=file_size,
        local_path=local_path,
    )
    db.add(video)
    await db.flush()
    video_id = str(video.id)

    background_tasks.add_task(
        _run_pipeline_bg,
        video_id=video_id,
        source_url=None,
        local_path=local_path,
        game=game,
        max_clips=max_clips,
        clip_duration=clip_duration,
        watermark=watermark,
    )

    return {
        "video_id":   video_id,
        "status":     "queued",
        "file_size":  file_size,
        "message":    "Upload received. Processing started in background.",
    }


@router.get("/", response_model=List[dict])
async def list_videos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all videos for the authenticated user, newest first."""
    result = await db.execute(
        select(Video)
        .where(Video.user_id == str(current_user.id))
        .order_by(Video.created_at.desc())
    )
    videos = result.scalars().all()
    return [
        {
            "id":             str(v.id),
            "title":          v.title,
            "game":           v.game or "",
            "source":         v.source or "",
            "status":         v.status,
            "source_url":     v.source_url,
            "clips_count":    len(v.clips) if v.clips else 0,
            "file_size_bytes": v.file_size_bytes,
            "created_at":     v.created_at.isoformat() if v.created_at else "",
        }
        for v in videos
    ]


@router.get("/{video_id}/status")
async def video_status(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Poll the processing status of a video.
    Returns current status + list of completed clips.
    """
    result = await db.execute(
        select(Video).where(
            Video.id == video_id,
            Video.user_id == str(current_user.id)
        )
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(404, "Video not found.")

    # Fetch associated clips
    clip_result = await db.execute(
        select(Clip).where(Clip.video_id == video_id)
    )
    clips = clip_result.scalars().all()

    return {
        "video_id":   str(video.id),
        "title":      video.title,
        "status":     video.status,
        "error_msg":  video.error_msg,
        "clips_count": len(clips),
        "clips": [
            {
                "id":         str(c.id),
                "title":      c.title,
                "clip_type":  c.clip_type,
                "duration":   c.duration,
                "score":      c.ai_score,
                "status":     c.status,
                "local_path": c.local_path,
                "cdn_url":    c.cdn_url,
                "created_at": c.created_at.isoformat() if c.created_at else "",
            }
            for c in clips
        ],
    }


@router.delete("/{video_id}", status_code=204)
async def delete_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a video and all its clips."""
    result = await db.execute(
        select(Video).where(
            Video.id == video_id,
            Video.user_id == str(current_user.id)
        )
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(404, "Video not found.")
    await db.delete(video)

