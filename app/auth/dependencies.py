"""FastAPI dependencies for authentication and role-based authorization."""

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.security import decode_access_token
from app.database import get_db
from app.models import User


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    cookie_token: str | None = Cookie(None, alias="access_token"),
    auth_header: str | None = Header(None, alias="Authorization"),
) -> User:
    """Decode the JWT from Authorization header or access_token cookie and return User."""
    token = None
    if auth_header:
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        else:
            token = auth_header.strip()

    if not token and cookie_token:
        token = cookie_token.strip()

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = await db.execute(
        select(User).options(selectinload(User.bakery)).where(User.id == payload["sub"])
    )
    user = user.scalar_one_or_none()

    if not user or user.isDeleted:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")

    # Check bakery status for bakers
    if user.role == "BAKER" and user.bakery:
        if user.bakery.isDeleted or user.bakery.status == "DELETED":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is no longer active")
        if user.bakery.status == "SUSPENDED":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bakery suspended")

    return user


async def get_optional_user(
    db: AsyncSession = Depends(get_db),
    cookie_token: str | None = Cookie(None, alias="access_token"),
    auth_header: str | None = Header(None, alias="Authorization"),
) -> User | None:
    """Like get_current_user but returns None instead of 401 when not logged in."""
    if not cookie_token and not auth_header:
        return None
    try:
        return await get_current_user(db=db, cookie_token=cookie_token, auth_header=auth_header)
    except HTTPException:
        return None


def require_role(*roles: str):
    """Return a dependency that enforces the user has one of the given roles."""

    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return checker


require_baker = require_role("BAKER")
require_admin = require_role("SUPER_ADMIN")
require_authenticated = get_current_user
