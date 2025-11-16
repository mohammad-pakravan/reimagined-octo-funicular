"""
Database connection and session management using SQLAlchemy async.
Handles MySQL connection pooling and session creation.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from typing import AsyncGenerator

from config.settings import settings
from db.models import Base


# Create async engine with connection pooling
engine = create_async_engine(
    settings.mysql_url,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Verify connections before using
    pool_size=settings.DB_POOL_SIZE,  # Connection pool size (default: 150)
    max_overflow=settings.DB_MAX_OVERFLOW,  # Maximum overflow connections (default: 50)
    pool_recycle=3600,  # Recycle connections after 1 hour
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get database session.
    Yields a database session and ensures it's closed after use.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database by creating all tables.
    Call this once when the application starts.
    """
    async with engine.begin() as conn:
        # Create all tables defined in models
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Close database connections.
    Call this when shutting down the application.
    """
    await engine.dispose()


async def run_migration(migration_file: str) -> None:
    """
    Run a SQL migration file.
    
    Args:
        migration_file: Path to the SQL migration file
    """
    import os
    import logging
    import re
    
    logger = logging.getLogger(__name__)
    
    if not os.path.exists(migration_file):
        logger.warning(f"Migration file not found: {migration_file}")
        return
    
    try:
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Split by semicolon, but preserve prepared statements
        # Remove comments first
        lines = sql_content.split('\n')
        cleaned_lines = []
        for line in lines:
            # Remove single-line comments (but keep the line if it has content)
            if '--' in line:
                comment_pos = line.find('--')
                # Only remove if -- is not inside a string
                if comment_pos >= 0:
                    before_comment = line[:comment_pos].strip()
                    if before_comment:
                        cleaned_lines.append(before_comment)
                    else:
                        # Empty line after removing comment
                        cleaned_lines.append('')
                else:
                    cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)
        
        cleaned_content = '\n'.join(cleaned_lines)
        
        # Split by semicolon, but be careful with prepared statements
        # Simple approach: split by semicolon and newline
        # Remove empty lines and trim
        statements = []
        for stmt in re.split(r';\s*\n', cleaned_content):
            stmt = stmt.strip()
            if stmt and not stmt.startswith('--'):
                statements.append(stmt)
        
        # Execute each statement
        async with engine.begin() as conn:
            for statement in statements:
                if statement:
                    try:
                        await conn.execute(text(statement))
                        logger.debug(f"✅ Executed migration statement")
                    except Exception as e:
                        # If column/index already exists, that's okay
                        error_str = str(e)
                        if "Duplicate column name" in error_str or "Duplicate key name" in error_str or "already exists" in error_str.lower():
                            logger.info(f"ℹ️ Column/index already exists, skipping")
                        else:
                            # Re-raise if it's a real error
                            logger.error(f"❌ Migration statement failed: {e}")
                            logger.error(f"Failed statement: {statement[:100]}...")
                            raise
        
        logger.info(f"✅ Migration completed: {migration_file}")
    except Exception as e:
        logger.error(f"❌ Failed to run migration {migration_file}: {e}")
        raise
