"""
Integration tests for the cakes endpoints (CRUD for bakers).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bakery, Cake, Category, User
from tests.conftest import admin_token, baker_token


@pytest.mark.asyncio
class TestCakesEndpoints:

    async def test_create_cake(self, client: AsyncClient, bakery: Bakery, category: Category, baker_user: User):
        client.cookies.set("access_token", baker_token(baker_user))
        
        payload = {
            "categoryId": category.id,
            "name": "Strawberry Shortcake",
            "description": "Fresh strawberries",
            "price": 4000,
            "images": ["http://example.com/strawberry.jpg"],
            "sizeOptions": [{"label": "1kg", "priceModifier": 4000}, {"label": "2kg", "priceModifier": 7500}],
            "isAvailable": True,
            "isFeatured": True
        }
        
        response = await client.post("/api/cakes", json=payload)
        assert response.status_code == 201
        
        data = response.json()
        assert data["id"] is not None
        assert data["name"] == "Strawberry Shortcake"
        assert data["slug"] == "strawberry-shortcake"
        assert data["price"] == 4000
        assert data["bakeryId"] == bakery.id

    async def test_create_cake_unauthorized(self, client: AsyncClient, category: Category):
        payload = {
            "categoryId": category.id,
            "name": "Strawberry Shortcake",
            "price": 4000,
            "images": ["http://example.com/strawberry.jpg"],
            "isAvailable": True,
            "isFeatured": True
        }
        # No token
        response = await client.post("/api/cakes", json=payload)
        assert response.status_code == 401
        
    async def test_create_cake_wrong_role(self, client: AsyncClient, category: Category, admin_user: User):
        client.cookies.set("access_token", admin_token(admin_user))
        payload = {
            "categoryId": category.id,
            "name": "Strawberry Shortcake",
            "price": 4000,
            "images": ["http://example.com/strawberry.jpg"],
            "isAvailable": True,
            "isFeatured": True
        }
        # Admins can't create cakes for a bakery directly through this endpoint
        response = await client.post("/api/cakes", json=payload)
        assert response.status_code == 403

    async def test_update_cake(self, client: AsyncClient, baker_user: User, cake: Cake, category: Category):
        client.cookies.set("access_token", baker_token(baker_user))
        
        payload = {
            "categoryId": category.id,
            "name": "Updated Cake Name",
            "description": "Updated description",
            "price": 5000,
            "discountPrice": 4500,
            "images": ["http://example.com/updated.jpg"],
            "isAvailable": False,
            "isFeatured": False
        }
        
        response = await client.put(f"/api/cakes/{cake.id}", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "Updated Cake Name"
        assert data["price"] == 5000
        assert data["discountPrice"] == 4500
        assert data["isAvailable"] is False

    async def test_update_other_bakery_cake_fails(self, client: AsyncClient, db_session: AsyncSession, cake: Cake):
        # Create a second baker
        other_baker = User(name="Other", email="other@test.com", passwordHash="h", role="BAKER")
        db_session.add(other_baker)
        await db_session.commit()
        await db_session.refresh(other_baker)
        
        other_bakery = Bakery(ownerId=other_baker.id, slug="other", name="Other", whatsappNumber="123", city="N", status="APPROVED")
        db_session.add(other_bakery)
        await db_session.commit()
        
        client.cookies.set("access_token", baker_token(other_baker))
        
        payload = {
            "categoryId": cake.categoryId,
            "name": "Hacked Cake",
            "price": 100,
            "images": ["http://example.com/hacked.jpg"],
            "isAvailable": True,
            "isFeatured": False
        }
        
        response = await client.put(f"/api/cakes/{cake.id}", json=payload)
        assert response.status_code == 404 # Should not find the cake for this baker

    async def test_delete_cake(self, client: AsyncClient, baker_user: User, cake: Cake, db_session: AsyncSession):
        client.cookies.set("access_token", baker_token(baker_user))
        
        response = await client.delete(f"/api/cakes/{cake.id}")
        assert response.status_code == 200
        
        # Verify deletion
        c = await db_session.scalar(select(Cake).where(Cake.id == cake.id))
        assert c is None
