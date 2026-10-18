"""
Unit tests for ORM models — creation, defaults, relationships.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Bakery,
    BakeryStatus,
    Cake,
    Category,
    Order,
    OrderStatus,
    Review,
    Role,
    User,
    generate_id,
)


class TestUserModel:

    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession):
        user = User(
            name="Test User",
            email="test@example.com",
            passwordHash="fakehash",
            role=Role.BAKER.value,
        )
        db_session.add(user)
        await db_session.commit()

        result = await db_session.scalar(select(User).where(User.email == "test@example.com"))
        assert result is not None
        assert result.name == "Test User"
        assert result.role == "BAKER"
        assert result.isDeleted is False

    @pytest.mark.asyncio
    async def test_user_has_auto_id(self, db_session: AsyncSession):
        user = User(name="Auto ID User", email="auto@id.com", passwordHash="hash")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        assert user.id is not None
        assert len(user.id) > 0

    @pytest.mark.asyncio
    async def test_user_email_unique(self, db_session: AsyncSession):
        u1 = User(name="A", email="dup@test.com", passwordHash="h")
        u2 = User(name="B", email="dup@test.com", passwordHash="h")
        db_session.add(u1)
        await db_session.commit()
        db_session.add(u2)
        with pytest.raises(Exception):
            await db_session.commit()


class TestBakeryModel:

    @pytest.mark.asyncio
    async def test_create_bakery(self, db_session: AsyncSession, baker_user: User):
        bakery = Bakery(
            ownerId=baker_user.id,
            slug="unit-test-bakery",
            name="Unit Test Bakery",
            whatsappNumber="+254700000099",
            city="Nairobi",
            status=BakeryStatus.PENDING.value,
        )
        db_session.add(bakery)
        await db_session.commit()
        await db_session.refresh(bakery)

        assert bakery.id is not None
        assert bakery.status == "PENDING"
        assert bakery.isDeleted is False

    @pytest.mark.asyncio
    async def test_bakery_slug_unique(self, db_session: AsyncSession, baker_user: User):
        b1 = Bakery(
            ownerId=baker_user.id,
            slug="same-slug",
            name="B1",
            whatsappNumber="+254700000001",
            city="Nairobi",
        )
        db_session.add(b1)
        await db_session.commit()

        # Create another user to avoid the ownerId unique constraint
        u2 = User(name="U2", email="u2@test.com", passwordHash="h", role=Role.BAKER.value)
        db_session.add(u2)
        await db_session.commit()

        b2 = Bakery(
            ownerId=u2.id,
            slug="same-slug",
            name="B2",
            whatsappNumber="+254700000002",
            city="Mombasa",
        )
        db_session.add(b2)
        with pytest.raises(Exception):
            await db_session.commit()


class TestCakeModel:

    @pytest.mark.asyncio
    async def test_create_cake(self, db_session: AsyncSession, bakery: Bakery, category: Category):
        c = Cake(
            bakeryId=bakery.id,
            categoryId=category.id,
            name="Choco Cake",
            slug="choco-cake",
            price=3000,
            images=["https://img.co/1.jpg"],
        )
        db_session.add(c)
        await db_session.commit()
        await db_session.refresh(c)

        assert c.id is not None
        assert c.isAvailable is True
        assert c.isFeatured is False


class TestOrderModel:

    @pytest.mark.asyncio
    async def test_create_order(self, db_session: AsyncSession, bakery: Bakery):
        o = Order(
            bakeryId=bakery.id,
            customerName="John Doe",
            customerPhone="+254712345678",
            items=[{"name": "Vanilla Cake", "qty": 1, "price": 2000}],
            totalAmount=2000,
            status=OrderStatus.PENDING.value,
            channel="WHATSAPP",
        )
        db_session.add(o)
        await db_session.commit()
        await db_session.refresh(o)

        assert o.id is not None
        assert o.status == "PENDING"
        assert o.totalAmount == 2000


class TestReviewModel:

    @pytest.mark.asyncio
    async def test_create_review(self, db_session: AsyncSession, bakery: Bakery):
        r = Review(
            bakeryId=bakery.id,
            customerName="Customer",
            rating=5,
            comment="Great cake!",
        )
        db_session.add(r)
        await db_session.commit()
        await db_session.refresh(r)

        assert r.id is not None
        assert r.rating == 5


class TestGenerateId:

    def test_id_is_string(self):
        assert isinstance(generate_id(), str)

    def test_id_is_unique(self):
        ids = {generate_id() for _ in range(100)}
        assert len(ids) == 100

    def test_id_is_valid_uuid(self):
        import uuid as uuid_lib

        val = generate_id()
        assert len(val) == 36
        parsed = uuid_lib.UUID(val)
        assert parsed.version == 4
