"""
Shared fixtures for the Crumbly backend test suite.

Uses an async in-memory SQLite database so tests are fast and isolated.
Every test function gets its own transaction that is rolled back automatically.
"""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-key-1234567890")

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.auth.security import create_access_token, hash_password
from app.config import Settings, get_settings
from app.database import get_db
from app.main import app
from app.models import (
    Bakery,
    BakeryStatus,
    Base,
    Cake,
    Category,
    Order,
    OrderStatus,
    Role,
    User,
    generate_id,
)

# ──────────────────── In-memory async SQLite engine for tests

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


# ──────────────────── Override settings for tests

def get_test_settings():
    return Settings(
        database_url=TEST_DATABASE_URL,
        jwt_secret="test-secret-key-for-testing-only",
        cors_origins="http://localhost:3000",
    )


# ──────────────────── Fixtures


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Use a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh database session for unit tests."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Yield an httpx AsyncClient wired to our FastAPI app with the test DB.
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = get_test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ──────────────────── Factory fixtures


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create and return a SUPER_ADMIN user."""
    user = User(
        id=generate_id(),
        name="Test Admin",
        email="admin@test.com",
        passwordHash=hash_password("Admin123!"),
        role=Role.SUPER_ADMIN.value,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def baker_user(db_session: AsyncSession) -> User:
    """Create and return a BAKER user."""
    user = User(
        id=generate_id(),
        name="Test Baker",
        email="baker@test.com",
        passwordHash=hash_password("Baker123!"),
        phone="+254700000001",
        role=Role.BAKER.value,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def bakery(db_session: AsyncSession, baker_user: User) -> Bakery:
    """Create and return an APPROVED bakery owned by baker_user."""
    b = Bakery(
        id=generate_id(),
        ownerId=baker_user.id,
        slug="test-bakery",
        name="Test Bakery",
        description="A bakery for testing",
        whatsappNumber="+254700000001",
        city="Nairobi",
        status=BakeryStatus.APPROVED.value,
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


@pytest_asyncio.fixture
async def category(db_session: AsyncSession) -> Category:
    """Create and return a test category."""
    cat = Category(
        id=generate_id(),
        name="Birthday Cakes",
        slug="birthday-cakes",
        icon="cake",
    )
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)
    return cat


@pytest_asyncio.fixture
async def cake(db_session: AsyncSession, bakery: Bakery, category: Category) -> Cake:
    """Create and return a test cake."""
    c = Cake(
        id=generate_id(),
        bakeryId=bakery.id,
        categoryId=category.id,
        name="Test Vanilla Cake",
        slug="test-vanilla-cake",
        description="A delicious test cake",
        price=2500,
        images=["https://placehold.co/600x400"],
        isAvailable=True,
        isFeatured=True,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest_asyncio.fixture
async def order(db_session: AsyncSession, bakery: Bakery, cake: Cake) -> Order:
    """Create and return a test order."""
    o = Order(
        id=generate_id(),
        bakeryId=bakery.id,
        customerName="Alice Mwangi",
        customerPhone="+254712345678",
        items=[{"cakeId": cake.id, "name": cake.name, "qty": 2, "price": cake.price}],
        totalAmount=cake.price * 2,
        status=OrderStatus.PENDING.value,
        channel="WHATSAPP",
    )
    db_session.add(o)
    await db_session.commit()
    await db_session.refresh(o)
    return o


# ──────────────────── Token helpers


def admin_token(admin_user: User) -> str:
    return create_access_token(data={"sub": admin_user.id, "role": admin_user.role})


def baker_token(baker_user: User) -> str:
    return create_access_token(data={"sub": baker_user.id, "role": baker_user.role})
