from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

def get_async_database_url(url: str) -> str:
    """Normalize PostgreSQL URLs (Neon, Supabase, etc.) for asyncpg driver."""
    clean = url.strip()
    if clean.startswith("postgres://"):
        clean = clean.replace("postgres://", "postgresql+asyncpg://", 1)
    elif clean.startswith("postgresql://"):
        clean = clean.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "asyncpg" in clean:
        clean = (
            clean.replace("&channel_binding=require", "")
            .replace("channel_binding=require&", "")
            .replace("channel_binding=require", "")
            .replace("sslmode=require", "ssl=require")
            .rstrip("&")
            .rstrip("?")
        )
    return clean


# Create the async engine
engine = create_async_engine(
    get_async_database_url(settings.DATABASE_URL),
    echo=settings.APP_ENV == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy ORM models."""
    pass


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """Dependency that yields an async DB session and always closes it."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
