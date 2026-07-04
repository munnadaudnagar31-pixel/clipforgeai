"""ClipForge AI â€” Clips API Routes (CRUD + download)

GET  /api/clips/          â€” list user's clips (filterable by game/status/type)
GET  /api/clips/{id}      â€” get clip details + download URL
DELETE /api/clips/{id}    â€” delete clip
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


from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import User, Clip
from app.api.auth import get_current_user
from app.config import settings

router = APIRouter()


# â”€â”€ Schemas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class ClipResponse(BaseModel):
    id:            str
    title:         str
    clip_type:     str
    game:          str
    duration:      float
    ai_score:      float
    status:        str
    cdn_url:       Optional[str] = None
    local_path:    Optional[str] = None
    thumbnail_url: Optional[str] = None
    view_count:    int
    has_music:     bool
    is_watermarked: bool
    created_at:    str

    class Config:
        from_attributes = True


def _clip_to_response(c: Clip) -> ClipResponse:
    return ClipResponse(
        id=str(c.id),
        title=c.title,
        clip_type=c.clip_type,
        game=c.game or "",
        duration=c.duration,
        ai_score=c.ai_score or 0.0,
        status=c.status,
        cdn_url=c.cdn_url,
        local_path=c.local_path,
        thumbnail_url=c.thumbnail_url,
        view_count=c.view_count,
        has_music=c.has_music,
        is_watermarked=c.is_watermarked,
        created_at=c.created_at.isoformat() if c.created_at else "",
    )


# â”€â”€ Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/", response_model=List[ClipResponse])
async def list_clips(
    game:      Optional[str] = None,
    status:    Optional[str] = None,
    clip_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all clips for the authenticated user, with optional filters."""
    query = select(Clip).where(Clip.user_id == str(current_user.id))
    if game:      query = query.where(Clip.game == game)
    if status:    query = query.where(Clip.status == status)
    if clip_type: query = query.where(Clip.clip_type == clip_type)
    query = query.order_by(Clip.created_at.desc())

    result = await db.execute(query)
    clips = result.scalars().all()
    return [_clip_to_response(c) for c in clips]


@router.get("/{clip_id}")
async def get_clip(
    clip_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get clip details + a download URL (signed S3 or local path)."""
    result = await db.execute(
        select(Clip).where(Clip.id == clip_id, Clip.user_id == str(current_user.id))
    )
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(404, "Clip not found.")
    if clip.status != "ready":
        raise HTTPException(400, f"Clip is not ready yet (status: {clip.status}).")

    # Build download URL
    download_url = None
    if clip.cdn_url:
        download_url = clip.cdn_url
    elif clip.s3_key and settings.AWS_ACCESS_KEY_ID:
        import boto3
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        download_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_RENDERED, "Key": clip.s3_key},
            ExpiresIn=900,
        )
    elif clip.local_path:
        # Dev mode: serve directly via /api/clips/{id}/file
        download_url = f"/api/clips/{clip_id}/file"

    return {**_clip_to_response(clip).model_dump(), "download_url": download_url}


@router.get("/{clip_id}/file")
async def serve_clip_file(
    clip_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Dev mode: stream the rendered clip file directly from local storage.
    In production, use signed S3/CloudFront URLs instead.
    """
    result = await db.execute(
        select(Clip).where(Clip.id == clip_id, Clip.user_id == str(current_user.id))
    )
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(404, "Clip not found.")
    if not clip.local_path or not Path(clip.local_path).exists():
        raise HTTPException(404, "Clip file not found on disk.")

    # Increment view count
    clip.view_count += 1

    return FileResponse(
        path=clip.local_path,
        media_type="video/mp4",
        filename=f"{clip.title.replace(' ', '_')}.mp4",
    )


@router.delete("/{clip_id}", status_code=204)
async def delete_clip(
    clip_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Clip).where(Clip.id == clip_id, Clip.user_id == str(current_user.id))
    )
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(404, "Clip not found.")

    # Try to delete local file
    if clip.local_path:
        try:
            Path(clip.local_path).unlink(missing_ok=True)
        except Exception:
            pass

    await db.delete(clip)

