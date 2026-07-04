"""ClipForge AI â€” Database session management

Supports:
  â€¢ SQLite (local dev):   DATABASE_URL=sqlite+aiosqlite:///./clipforge.db
  â€¢ PostgreSQL (prod):    DATABASE_URL=postgresql+asyncpg://user:pass@host/db
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


from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool
from .config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# SQLite needs StaticPool + check_same_thread=False; Postgres gets connection pool.
if _is_sqlite:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency â€” yields a DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

