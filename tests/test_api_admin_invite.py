"""Integration tests for Super Admin invitation, listing, and password setup flow."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PasswordResetToken, Role, User


from tests.conftest import admin_token, baker_token


@pytest.mark.asyncio
class TestAdminInvitationFlow:

    async def test_list_admins_as_admin(
        self, client: AsyncClient, admin_user: User
    ):
        token = admin_token(admin_user)
        response = await client.get(
            "/api/admin/admins",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(a["email"] == admin_user.email for a in data)

    async def test_non_admin_cannot_access_or_invite(
        self, client: AsyncClient, baker_user: User
    ):
        token = baker_token(baker_user)
        res_list = await client.get(
            "/api/admin/admins",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_list.status_code == 403

        res_invite = await client.post(
            "/api/admin/admins/invite",
            json={"email": "newadmin@test.com", "name": "New Admin"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_invite.status_code == 403

    async def test_invite_super_admin_and_set_password_flow(
        self, client: AsyncClient, admin_user: User, db_session: AsyncSession
    ):
        token = admin_token(admin_user)
        invite_email = "invited.admin@crumbly.co.ke"

        # 1. Invite a new super admin
        invite_res = await client.post(
            "/api/admin/admins/invite",
            json={"email": invite_email, "name": "Grace Hopper"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert invite_res.status_code == 200
        invite_data = invite_res.json()
        assert invite_data["email"] == invite_email
        assert "token" in invite_data
        assert "setupUrl" in invite_data
        reset_token_str = invite_data["token"]

        # 2. Verify database record
        user = await db_session.scalar(select(User).where(User.email == invite_email))
        assert user is not None
        assert user.role == Role.SUPER_ADMIN.value
        assert user.passwordHash == "!"  # Unusable password hash

        # 3. Attempting to log in before setting password MUST fail
        fail_login = await client.post(
            "/api/auth/login",
            json={"email": invite_email, "password": "AnyPassword123!"},
        )
        assert fail_login.status_code == 401

        # 4. Invited admin completes setup via /api/auth/reset-password
        new_password = "SuperSecretSecurePassword99!"
        reset_res = await client.post(
            "/api/auth/reset-password",
            json={"token": reset_token_str, "password": new_password},
        )
        assert reset_res.status_code == 200

        # 5. Token is now consumed
        token_in_db = await db_session.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token == reset_token_str)
        )
        assert token_in_db is None

        # 6. Admin can now log in successfully with newly chosen password!
        success_login = await client.post(
            "/api/auth/login",
            json={"email": invite_email, "password": new_password},
        )
        assert success_login.status_code == 200
        login_data = success_login.json()
        assert login_data["user"]["email"] == invite_email
        assert login_data["user"]["role"] == Role.SUPER_ADMIN.value
        assert "token" in login_data

        # 7. List admins confirms status is now active (not pending invite)
        list_res = await client.get(
            "/api/admin/admins",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_res.status_code == 200
        admin_entry = next((a for a in list_res.json() if a["email"] == invite_email), None)
        assert admin_entry is not None
        assert admin_entry["isPendingInvite"] is False
