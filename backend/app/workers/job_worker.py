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
ClipForge AI â€” Celery Background Worker
Processes: video download â†’ AI detection â†’ rendering â†’ S3/local save â†’ DB update

Uses plain string status/plan values throughout (no Enum objects).
Sync SQLAlchemy session used inside Celery task (not async).
"""

import os
import uuid
import tempfile
from pathlib import Path
from typing import Optional

from celery import Celery
from sqlalchemy import create_engine, update, select
from sqlalchemy.orm import sessionmaker

from app.config import settings


# â”€â”€ Celery App â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
celery_app = Celery(
    "clipforge",
    broker=settings.CELERY_BROKER,
    backend=settings.CELERY_BACKEND,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_max_tasks_per_child=50,
    task_time_limit=3600,
    task_soft_time_limit=3300,
)


# â”€â”€ S3 Helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class S3Client:
    def __init__(self):
        import boto3
        self.client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

    def upload(
        self,
        local_path: str,
        bucket: str,
        s3_key: str,
        content_type: str = "video/mp4",
    ) -> str:
        self.client.upload_file(
            local_path, bucket, s3_key,
            ExtraArgs={"ContentType": content_type, "ACL": "private"},
        )
        if settings.CLOUDFRONT_DOMAIN:
            return f"https://{settings.CLOUDFRONT_DOMAIN}/{s3_key}"
        return f"https://{bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"

    def delete(self, bucket: str, s3_key: str) -> None:
        self.client.delete_object(Bucket=bucket, Key=s3_key)


# â”€â”€ Sync DB Session Factory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _make_sync_session():
    """
    Create a synchronous SQLAlchemy session factory.
    Converts async driver URLs to their sync equivalents:
      postgresql+asyncpg  â†’ postgresql+psycopg2
      sqlite+aiosqlite    â†’ sqlite
    """
    url = (
        settings.DATABASE_URL
        .replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        .replace("sqlite+aiosqlite://", "sqlite://")
    )
    engine = create_engine(url, pool_pre_ping=True, connect_args=(
        {"check_same_thread": False} if url.startswith("sqlite") else {}
    ))
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


# â”€â”€ yt-dlp Downloader â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _download_video(url: str, output_dir: str) -> str:
    """Download a Twitch/YouTube VOD using yt-dlp. Returns local file path."""
    try:
        import yt_dlp
    except ImportError:
        raise RuntimeError("yt-dlp is not installed. Run: pip install yt-dlp")

    output_template = str(Path(output_dir) / "%(id)s.%(ext)s")
    ydl_opts = {
        "format":             "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "outtmpl":            output_template,
        "merge_output_format":"mp4",
        "quiet":              True,
        "no_warnings":        True,
        "writeinfojson":      False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # Normalise extension
        for ext in (".webm", ".mkv"):
            filename = filename.replace(ext, ".mp4")
    return filename


# â”€â”€ DB Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _update_video_status(video_id: str, status: str, Session) -> None:
    from app.models.models import Video
    with Session() as session:
        session.execute(
            update(Video).where(Video.id == video_id).values(status=status)
        )
        session.commit()


def _mark_video_failed(video_id: str, error: str, Session) -> None:
    from app.models.models import Video
    with Session() as session:
        session.execute(
            update(Video)
            .where(Video.id == video_id)
            .values(status="failed", error_msg=error[:2000])
        )
        session.commit()
    print(f"[Worker] Video {video_id} FAILED: {error[:200]}")


def _get_video_user_id(video_id: str, session) -> str:
    from app.models.models import Video
    row = session.execute(
        select(Video.user_id).where(Video.id == video_id)
    ).scalar_one_or_none()
    return str(row) if row else ""


# â”€â”€ Main Celery Task â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@celery_app.task(bind=True, name="process_video")
def process_video_task(
    self,
    video_id: str,
    source_url: Optional[str],
    s3_raw_key: Optional[str],
    game: str = "BGMI",
    max_clips: int = 5,
    clip_duration: int = 30,
    quality: str = "1080p",
    aspect: str = "9:16",
    watermark: bool = True,
    add_music: bool = False,
    user_plan: str = "free",
):
    """
    Full pipeline Celery task:
      1. Download video (URL or fetch from S3)
      2. Run AI detection (audio + CV)
      3. Render highlight clips (9:16 split-screen)
      4. Upload rendered clips to S3 (or save locally in dev mode)
      5. Update DB records
    """
    from app.models.models import Video, Clip
    from app.ai.pipeline import detect_highlights, render_clip_916, _get_video_duration
    from app.ai.reframer import generate_thumbnail

    Session = _make_sync_session()

    print(f"\n[Worker] Starting task for video_id={video_id}")

    with tempfile.TemporaryDirectory() as tmpdir:

        # â”€â”€ Step 1: Obtain raw video â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.update_state(state="PROGRESS", meta={"step": "downloading", "pct": 5})
        _update_video_status(video_id, "downloading", Session)

        if source_url:
            try:
                video_path = _download_video(source_url, tmpdir)
            except Exception as e:
                _mark_video_failed(video_id, str(e), Session)
                raise

        elif s3_raw_key:
            video_path = str(Path(tmpdir) / "raw.mp4")
            s3 = S3Client()
            s3.client.download_file(settings.S3_BUCKET_RAW, s3_raw_key, video_path)

        else:
            err = "No source_url or s3_raw_key provided"
            _mark_video_failed(video_id, err, Session)
            raise ValueError(err)

        # â”€â”€ Step 2: AI Detection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _update_video_status(video_id, "analyzing", Session)
        self.update_state(state="PROGRESS", meta={"step": "analyzing", "pct": 25})

        try:
            highlights = detect_highlights(
                video_path=video_path,
                game=game,
                max_clips=max_clips,
                clip_duration=clip_duration,
            )
        except Exception as e:
            _mark_video_failed(video_id, f"AI detection failed: {e}", Session)
            raise

        if not highlights:
            _mark_video_failed(video_id, "No highlights detected", Session)
            return {"status": "failed", "reason": "No highlights detected"}

        # â”€â”€ Step 3: Render clips â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.update_state(state="PROGRESS", meta={"step": "rendering", "pct": 55})
        render_dir = Path(tmpdir) / "rendered"
        render_dir.mkdir(parents=True, exist_ok=True)

        use_s3 = bool(settings.AWS_ACCESS_KEY_ID and settings.S3_BUCKET_RENDERED)
        s3 = S3Client() if use_s3 else None

        # Local storage for dev mode
        local_clips_dir = Path(settings.LOCAL_STORAGE_DIR) / "clips" / video_id
        if not use_s3:
            local_clips_dir.mkdir(parents=True, exist_ok=True)

        # â”€â”€ Step 4: Upload/save + update DB â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.update_state(state="PROGRESS", meta={"step": "uploading", "pct": 80})
        created_clip_ids = []

        with Session() as session:
            for i, hl in enumerate(highlights):
                clip_id   = str(uuid.uuid4())
                out_file  = str(render_dir / f"clip_{i+1}_{clip_id[:8]}.mp4")

                success = render_clip_916(
                    source_path=video_path,
                    output_path=out_file,
                    start_time=hl["start_time"],
                    duration=hl["duration"],
                    watermark=watermark and (user_plan == "free"),
                )

                if not success:
                    print(f"[Worker] Render failed for clip {i+1}, skipping.")
                    continue

                # Upload or copy to local storage
                cdn_url    = None
                local_path = None
                s3_key     = None
                thumb_url  = None

                if use_s3:
                    s3_key  = f"clips/{video_id}/{clip_id}.mp4"
                    cdn_url = s3.upload(out_file, settings.S3_BUCKET_RENDERED, s3_key)
                    # Thumbnail
                    try:
                        thumb_file = str(render_dir / f"thumb_{i}.jpg")
                        generate_thumbnail(out_file, 2.0, thumb_file)
                        thumb_key = f"thumbs/{video_id}/{clip_id}.jpg"
                        thumb_url = s3.upload(thumb_file, settings.S3_BUCKET_RENDERED, thumb_key, "image/jpeg")
                    except Exception as te:
                        print(f"[Worker] Thumbnail failed: {te}")
                else:
                    # Dev mode: move rendered file to persistent storage
                    import shutil
                    dest = str(local_clips_dir / f"{clip_id}.mp4")
                    shutil.move(out_file, dest)
                    local_path = dest

                clip_obj = Clip(
                    id=clip_id,
                    user_id=_get_video_user_id(video_id, session),
                    video_id=video_id,
                    title=hl["title"],
                    clip_type=hl["clip_type"],
                    start_time=float(hl["start_time"]),
                    end_time=float(hl["end_time"]),
                    duration=float(hl["duration"]),
                    ai_score=float(hl["score"]),
                    game=game,
                    aspect=aspect,
                    quality=quality,
                    fps=30,
                    status="ready",
                    s3_key=s3_key,
                    cdn_url=cdn_url,
                    local_path=local_path,
                    thumbnail_url=thumb_url,
                    is_watermarked=(watermark and user_plan == "free"),
                    has_music=add_music,
                    metadata_json={"events": hl.get("events", [])},
                )
                session.add(clip_obj)
                created_clip_ids.append(clip_id)

            # Mark video as done
            session.execute(
                update(Video)
                .where(Video.id == video_id)
                .values(
                    status="done",
                    events_detected=[
                        {"type": h["clip_type"], "ts": h["start_time"], "score": h["score"]}
                        for h in highlights
                    ],
                )
            )
            session.commit()

    self.update_state(state="PROGRESS", meta={"step": "done", "pct": 100})
    print(f"[Worker] Complete. Created {len(created_clip_ids)} clips.")
    return {"status": "done", "clips": created_clip_ids}

