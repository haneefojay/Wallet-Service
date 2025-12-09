import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config.database import Base
from app.config.settings import settings


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_client():
    """Create async test client."""
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    yield client


@pytest.fixture
async def db_session():
    """Create test database session."""
    # Use in-memory SQLite for testing or separate test database
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_local = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_local() as session:
        yield session
        await session.rollback()
    
    await engine.dispose()


@pytest.fixture
def jwt_secret_key():
    """Return JWT secret key for testing."""
    return "test-secret-key-do-not-use-in-production"


@pytest.fixture
def paystack_secret_key():
    """Return Paystack secret key for testing."""
    return "sk_test_1234567890abcdef"
