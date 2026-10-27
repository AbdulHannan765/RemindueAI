from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker
)
from .config import DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False
)


async def get_db():
    async with SessionLocal() as db:
        yield db