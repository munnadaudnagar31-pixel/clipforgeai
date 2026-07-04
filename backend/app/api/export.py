"""ClipForge AI â€” Export API Routes

Handles publishing clips to social platforms and tracking export history.
All model fields use plain strings (no Enum objects) â€” compatible with SQLite + Postgres.
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


from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import User, Clip, Export
from app.api.auth import get_current_user

router = APIRouter()

# Valid platform values
VALID_PLATFORMS = {"youtube", "tiktok", "instagram", "download"}


# â”€â”€ Schemas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class PublishRequest(BaseModel):
    clip_ids:    List[str]
    platforms:   List[str]           # ["youtube", "tiktok", "instagram", "download"]
    title:       Optional[str] = None
    description: Optional[str] = None
    tags:        List[str] = []
    schedule_at: Optional[str] = None  # ISO 8601 datetime string


class ExportHistoryItem(BaseModel):
    id:            str
    clip_id:       str
    platform:      str
    title:         Optional[str] = None
    status:        str
    published_url: Optional[str] = None
    view_count:    int
    published_at:  Optional[str] = None
    created_at:    str

    class Config:
        from_attributes = True


# â”€â”€ Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@router.post("/publish", status_code=202)
async def publish_clips(
    payload: PublishRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Publish one or more clips to one or more social platforms.
    Creates Export records and optionally enqueues Celery publish tasks.
    """
    results = []

    for clip_id in payload.clip_ids:
        # Verify clip ownership + readiness
        result = await db.execute(
            select(Clip).where(
                Clip.id == clip_id,
                Clip.user_id == str(current_user.id),
            )
        )
        clip = result.scalar_one_or_none()

        if not clip:
            results.append({"clip_id": clip_id, "status": "error", "reason": "not found"})
            continue

        if clip.status != "ready":
            results.append({
                "clip_id": clip_id,
                "status": "skipped",
                "reason": f"clip status is '{clip.status}', must be 'ready'",
            })
            continue

        for platform in payload.platforms:
            if platform not in VALID_PLATFORMS:
                results.append({
                    "clip_id": clip_id,
                    "platform": platform,
                    "status": "error",
                    "reason": f"unknown platform '{platform}'",
                })
                continue

            # Interpolate title tokens
            base_title = payload.title or clip.title
            title = (
                base_title
                .replace("{event_type}", clip.clip_type or "highlight")
                .replace("{game}", clip.game or "")
            )

            default_tags = [
                f"#{(clip.game or 'Gaming').replace(' ', '')}Clips",
                "#Shorts", "#ClipForge", "#AIHighlights",
            ]
            tags = payload.tags or default_tags

            # Schedule datetime
            scheduled_at = None
            if payload.schedule_at:
                try:
                    scheduled_at = datetime.fromisoformat(payload.schedule_at)
                except ValueError:
                    pass

            # Create Export record
            export = Export(
                clip_id=str(clip.id),
                user_id=str(current_user.id),
                platform=platform,      # plain string, not enum
                title=title,
                description=payload.description or "",
                tags=tags,
                status="pending",
                scheduled_at=scheduled_at,
            )
            db.add(export)
            await db.flush()  # get export.id

            # Try to enqueue Celery publish task (optional â€” fails silently in dev)
            try:
                from app.workers.publish_worker import publish_clip_task
                publish_clip_task.delay(
                    export_id=str(export.id),
                    clip_cdn_url=clip.cdn_url,
                    clip_local_path=clip.local_path,
                    platform=platform,
                    title=title,
                    description=payload.description or "",
                    tags=tags,
                    user_id=str(current_user.id),
                    scheduled_at=payload.schedule_at,
                )
            except Exception as e:
                print(f"[Export] Publish task not queued (dev mode): {e}")

            results.append({
                "clip_id":   clip_id,
                "platform":  platform,
                "export_id": str(export.id),
                "status":    "queued",
            })

    total_queued = sum(1 for r in results if r.get("status") == "queued")
    return {"results": results, "total_queued": total_queued}


@router.get("/history", response_model=List[ExportHistoryItem])
async def export_history(
    platform: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the user's export history, newest first."""
    query = select(Export).where(Export.user_id == str(current_user.id))

    if platform:
        if platform not in VALID_PLATFORMS:
            raise HTTPException(400, f"Unknown platform '{platform}'")
        query = query.where(Export.platform == platform)

    query = query.order_by(Export.created_at.desc()).limit(min(limit, 200))
    result = await db.execute(query)
    exports = result.scalars().all()

    return [
        ExportHistoryItem(
            id=str(e.id),
            clip_id=str(e.clip_id),
            platform=e.platform,        # plain string now
            title=e.title,
            status=e.status,
            published_url=e.published_url,
            view_count=e.view_count or 0,
            published_at=e.published_at.isoformat() if e.published_at else None,
            created_at=e.created_at.isoformat() if e.created_at else "",
        )
        for e in exports
    ]


@router.get("/stats")
async def export_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate export stats for the current user."""
    result = await db.execute(
        select(Export).where(Export.user_id == str(current_user.id))
    )
    exports = result.scalars().all()

    total_views = sum(e.view_count or 0 for e in exports)
    by_platform: dict = {}
    for e in exports:
        p = e.platform  # plain string
        by_platform.setdefault(p, {"total": 0, "published": 0, "views": 0})
        by_platform[p]["total"] += 1
        if e.status == "published":
            by_platform[p]["published"] += 1
        by_platform[p]["views"] += e.view_count or 0

    return {
        "total_exports":   len(exports),
        "total_published": sum(1 for e in exports if e.status == "published"),
        "total_views":     total_views,
        "by_platform":     by_platform,
    }

