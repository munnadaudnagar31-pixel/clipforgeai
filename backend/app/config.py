"""ClipForge AI â€” Configuration (reads from .env)

For local SQLite dev, set in your .env:
  DATABASE_URL=sqlite+aiosqlite:///./clipforge.db
  SECRET_KEY=dev-secret-key-change-in-production
"""


from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "ClipForge AI"
    APP_ENV:  str = "development"
    SECRET_KEY: str = "dev-secret-key-please-change-in-production-32c"
    DEBUG: bool = True

    # Database â€” defaults to local SQLite for zero-config local dev
    DATABASE_URL: str = "sqlite+aiosqlite:///./clipforge.db"

    # Redis / Celery (optional â€” workers disabled in dev mode)
    REDIS_URL:     str = "redis://localhost:6379/0"
    CELERY_BROKER: str = "redis://localhost:6379/0"
    CELERY_BACKEND: str = "redis://localhost:6379/1"

    # AWS S3 (leave empty for local dev â€” files saved locally)
    AWS_ACCESS_KEY_ID:     str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION:            str = "ap-south-1"
    S3_BUCKET_RAW:         str = "clipforge-raw-videos"
    S3_BUCKET_RENDERED:    str = "clipforge-rendered-clips"
    CLOUDFRONT_DOMAIN:     str = ""

    # Auth / JWT
    JWT_ALGORITHM:        str = "HS256"
    ACCESS_TOKEN_EXPIRE:  int = 3600       # 1 hour
    REFRESH_TOKEN_EXPIRE: int = 2592000    # 30 days

    # OAuth (optional)
    GOOGLE_CLIENT_ID:     str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    TWITCH_CLIENT_ID:     str = ""
    TWITCH_CLIENT_SECRET: str = ""

    # Stripe (optional)
    STRIPE_SECRET_KEY:     str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_PRO:      str = ""
    STRIPE_PRICE_CREATOR:  str = ""
    STRIPE_PRICE_AGENCY:   str = ""

    # YouTube / TikTok (optional)
    YOUTUBE_CLIENT_ID:     str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    TIKTOK_CLIENT_KEY:     str = ""
    TIKTOK_CLIENT_SECRET:  str = ""

    # Sentry (optional)
    SENTRY_DSN: str = ""

    # CORS â€” allow local static files & dev server
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "null",                    # file:// origin (open HTML directly)
        "https://clipforge.ai",
    ]

    # AI Settings
    YOLO_MODEL_PATH:         str = "models/yolov8_game_ui.pt"
    YOLO_BASE_MODEL:         str = "yolov8n.pt"
    CV_SAMPLE_FPS:           int = 2
    AUDIO_RMS_PERCENTILE:    float = 0.85
    MAX_CLIPS_PER_VIDEO:     int = 10
    DEFAULT_CLIP_DURATION:   int = 30
    HIGHLIGHT_WINDOW_BEFORE: int = 5

    # Local storage paths (dev mode when S3 is not configured)
    LOCAL_STORAGE_DIR: str = "./storage"   # relative to backend/

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

