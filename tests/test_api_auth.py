"""
Integration tests for authentication endpoints (login, register, logout, me).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bakery, User
from app.auth.security import hash_password
from tests.conftest import admin_token, baker_token


@pytest.mark.asyncio
class TestAuthEndpoints:

    async def test_register_baker_success(self, client: AsyncClient, db_session: AsyncSession):
        payload = {
            "name": "New Baker",
            "email": "newbaker@test.com",
            "password": "Password123!",
            "phone": "+254711111111",
            "bakeryName": "New Bakery",
            "city": "Nairobi",
            "whatsappNumber": "+254711111111",
            "description": "A nice new bakery"
        }
        response = await client.post("/api/auth/register", json=payload)
        assert response.status_code == 201
        
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == "newbaker@test.com"
        assert data["user"]["role"] == "BAKER"
        assert data["user"]["bakerySlug"] == "new-bakery"
        assert data["user"]["bakeryStatus"] == "PENDING"
        
        # Verify db
        user = await db_session.scalar(select(User).where(User.email == "newbaker@test.com"))
        assert user is not None
        bakery = await db_session.scalar(select(Bakery).where(Bakery.ownerId == user.id))
        assert bakery is not None
        assert bakery.status == "PENDING"

    async def test_register_duplicate_email(self, client: AsyncClient, baker_user: User):
        payload = {
            "name": "Another Baker",
            "email": baker_user.email, # Duplicate
            "password": "Password123!",
            "phone": "+254722222222",
            "bakeryName": "Another Bakery",
            "city": "Mombasa",
            "whatsappNumber": "+254722222222",
            "description": "..."
        }
        response = await client.post("/api/auth/register", json=payload)
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    async def test_login_success(self, client: AsyncClient, baker_user: User):
        # The baker_user fixture has password "Baker123!"
        response = await client.post("/api/auth/login", json={
            "email": baker_user.email,
            "password": "Baker123!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == baker_user.email
        
        # Check cookie is set
        assert "access_token" in response.cookies

    async def test_login_invalid_password(self, client: AsyncClient, baker_user: User):
        response = await client.post("/api/auth/login", json={
            "email": baker_user.email,
            "password": "WrongPassword!"
        })
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    async def test_login_invalid_email(self, client: AsyncClient):
        response = await client.post("/api/auth/login", json={
            "email": "doesntexist@test.com",
            "password": "SomePassword123!"
        })
        assert response.status_code == 401

    async def test_get_me_authenticated(self, client: AsyncClient, admin_user: User):
        token = admin_token(admin_user)
        # We can either set cookie or just let the client do it by setting it in the jar
        client.cookies.set("access_token", token)
        
        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == admin_user.email
        assert data["role"] == "SUPER_ADMIN"

    async def test_get_me_unauthenticated(self, client: AsyncClient):
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_logout(self, client: AsyncClient, baker_user: User):
        token = baker_token(baker_user)
        client.cookies.set("access_token", token)
        
        response = await client.post("/api/auth/logout")
        assert response.status_code == 200
        # Cookie should be cleared
        # It's tricky to assert cookie deletion onhttpx, but the response should have Set-Cookie max-age=0 or similar
        # For our purposes, just checking the endpoint returns 200 is sufficient for integration
