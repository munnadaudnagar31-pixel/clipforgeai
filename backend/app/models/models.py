"""ClipForge AI â€” SQLAlchemy ORM Models (DB-agnostic: SQLite + PostgreSQL)"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    ForeignKey, Enum, JSON, Text, BigInteger
)
from sqlalchemy.orm import relationship
import enum

from backend.app.database import Base

# â”€â”€ String UUID helper (works on SQLite & PostgreSQL) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _uuid():
    return str(uuid.uuid4())

def _now():
    return datetime.now(timezone.utc)

# â”€â”€ Enums â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class PlanEnum(str, enum.Enum):
    free     = "free"
    pro      = "pro"
    creator  = "creator"
    agency   = "agency"

class VideoStatusEnum(str, enum.Enum):
    downloading = "downloading"
    analyzing   = "analyzing"
    queued      = "queued"
    done        = "done"
    failed      = "failed"

class ClipStatusEnum(str, enum.Enum):
    rendering = "rendering"
    ready     = "ready"
    failed    = "failed"

class ClipTypeEnum(str, enum.Enum):
    kill    = "kill"
    funny   = "funny"
    victory = "victory"
    audio   = "audio"
    chat    = "chat"

class ExportPlatformEnum(str, enum.Enum):
    youtube   = "youtube"
    tiktok    = "tiktok"
    instagram = "instagram"
    download  = "download"

# â”€â”€ User â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    # Use String for UUID so it works on both SQLite and PostgreSQL
    id         = Column(String(36), primary_key=True, default=_uuid)
    email      = Column(String(255), unique=True, nullable=False, index=True)
    name       = Column(String(255), nullable=False)
    avatar_url = Column(Text)
    password_hash = Column(Text)               # null for OAuth users

    # OAuth
    google_id  = Column(String(255), unique=True, index=True)
    twitch_id  = Column(String(255), unique=True, index=True)
    twitch_token  = Column(Text)
    youtube_token = Column(Text)
    tiktok_token  = Column(Text)

    # Subscription
    plan              = Column(String(20), default="free", nullable=False)
    stripe_customer_id   = Column(String(255))
    stripe_subscription_id = Column(String(255))
    plan_expires_at   = Column(DateTime)

    # Usage (monthly, reset by cron)
    clips_used_this_month = Column(Integer, default=0, nullable=False)

    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    # Relationships
    videos  = relationship("Video",  back_populates="user", cascade="all, delete-orphan")
    clips   = relationship("Clip",   back_populates="user", cascade="all, delete-orphan")
    exports = relationship("Export", back_populates="user")

    @property
    def plan_enum(self):
        return PlanEnum(self.plan)

# â”€â”€ Video â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class Video(Base):
    __tablename__ = "videos"
    __table_args__ = {'extend_existing': True}

    id         = Column(String(36), primary_key=True, default=_uuid)
    user_id    = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    title      = Column(String(500), nullable=False)
    source_url = Column(Text)                    # original URL
    game       = Column(String(100))             # BGMI, VALORANT, etc.
    source     = Column(String(50))              # twitch | youtube | upload
    duration_s = Column(Integer)                 # seconds
    file_size_bytes = Column(BigInteger)
    s3_raw_key = Column(Text)                    # S3 key for raw video
    local_path = Column(Text)                    # local file path (dev mode)

    status     = Column(String(30), default="queued", nullable=False)
    job_id     = Column(String(255))             # Celery task ID
    error_msg  = Column(Text)

    # AI results (stored as JSON strings on SQLite)
    events_detected = Column(JSON, default=list)  # [{type, timestamp, score}]
    audio_peaks     = Column(JSON, default=list)  # [{timestamp, rms}]
    chat_spikes     = Column(JSON, default=list)

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    # Relationships
    user  = relationship("User",  back_populates="videos")
    clips = relationship("Clip",  back_populates="video", cascade="all, delete-orphan")

# â”€â”€ Clip â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class Clip(Base):
    __tablename__ = "clips"
    __table_args__ = {'extend_existing': True}

    id       = Column(String(36), primary_key=True, default=_uuid)
    user_id  = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=False)

    title      = Column(String(500), nullable=False)
    clip_type  = Column(String(20), nullable=False)      # kill|funny|victory|audio|chat
    start_time = Column(Float, nullable=False)
    end_time   = Column(Float, nullable=False)
    duration   = Column(Float, nullable=False)

    ai_score   = Column(Float)
    game       = Column(String(100))
    aspect     = Column(String(20), default="9:16")
    quality    = Column(String(20), default="1080p")
    fps        = Column(Integer, default=60)

    status     = Column(String(20), default="rendering", nullable=False)
    s3_key     = Column(Text)
    cdn_url    = Column(Text)
    local_path = Column(Text)                    # rendered clip local path (dev)
    thumbnail_url = Column(Text)
    error_msg  = Column(Text)

    view_count   = Column(Integer, default=0)
    is_watermarked = Column(Boolean, default=True)
    has_music    = Column(Boolean, default=False)
    has_sfx      = Column(Boolean, default=False)
    metadata_json = Column(JSON, default=dict)

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    # Relationships
    user    = relationship("User",   back_populates="clips")
    video   = relationship("Video",  back_populates="clips")
    exports = relationship("Export", back_populates="clip", cascade="all, delete-orphan")

# â”€â”€ Export â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class Export(Base):
    __tablename__ = "exports"
    __table_args__ = {'extend_existing': True}

    id         = Column(String(36), primary_key=True, default=_uuid)
    clip_id    = Column(String(36), ForeignKey("clips.id"), nullable=False)
    user_id    = Column(String(36), ForeignKey("users.id"), nullable=False)

    platform   = Column(String(30), nullable=False)
    platform_video_id = Column(String(255))
    published_url     = Column(Text)
    title      = Column(String(500))
    description = Column(Text)
    tags       = Column(JSON, default=list)
    status     = Column(String(50), default="pending")
    error_msg  = Column(Text)
    view_count = Column(Integer, default=0)

    scheduled_at = Column(DateTime)
    published_at = Column(DateTime)
    created_at   = Column(DateTime, default=_now)

    # Relationships
    clip = relationship("Clip", back_populates="exports")
    user = relationship("User", back_populates="exports")

