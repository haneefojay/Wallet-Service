from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config.settings import settings

# Automatically convert DATABASE_URL to use asyncpg if needed
database_url = settings.DATABASE_URL
if database_url.startswith("postgresql://"):
    # Replace postgresql:// with postgresql+asyncpg:// for async support
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif not database_url.startswith("postgresql+asyncpg://"):
    # If it's already using a different async driver, keep it
    pass

# Create async engine
engine = create_async_engine(
    database_url,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
)

# Create async session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base for all models
Base = declarative_base()


async def get_db():
    """Dependency for database session in routes."""
    async with async_session() as session:
        yield session
