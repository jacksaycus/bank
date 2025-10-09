import asyncio
from typing import AsyncGenerator

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger()

engine = create_async_engine(settings.DATABASE_URL,
                             poolclass=AsyncAdaptedQueuePool,
                             pool_pre_ping=True,
                             pool_size=5,
                             max_overflow=10,
                             pool_timeout=30,
                             pool_recycle=1800,
                             )

async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)


async def get_session() -> AsyncGenerator[AsyncSession,None]:
    session = async_session()
    try:
        yield session
    except Exception as e:
        logger.error(f"Database session error: {e}")
        if session:
            try:
                await session.rollback()
                logger.info("successfully rolled back session after error")
            except Exception as rollback_error:
                logger.error(f"Error during session rollback:{rollback_error}")
        raise
    finally:
        if session:
            try:
                await session.close()
                logger.debug("Database session closed succefully")
            except Exception as close_error:
                logger.error(f"Error closing database session: {close_error}") 

async def init_db() -> None:
    try:
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                async with engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
                logger.info("Database connection verified succefully")
                break
            except Exception:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Failed to verify database connection after{max_retries} attempts"
                    )
                    raise
                logger.warning(f"Database connection attempt {attempt + 1}")

                await asyncio.sleep(retry_delay * (attempt +1)) 

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise