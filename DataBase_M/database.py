from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.engine import make_url

from .config import DATABASE_URL

# Force PostgreSQL to use asyncpg.
database_url = make_url(DATABASE_URL)

if database_url.drivername in ("postgres", "postgresql"):
    database_url = database_url.set(
        drivername="postgresql+asyncpg"
    )

engine = create_async_engine(
    database_url,
    pool_size=3,
    max_overflow=2,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def get_db():
    async with SessionLocal() as db:
        yield db
