import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.security import create_access_token, hash_password, verify_password
from app.config import get_settings
from app.database import get_db
from app.models import Bakery, BakeryStatus, PasswordResetToken, Role, User
from app.utils.email import send_password_reset_email
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterBakerRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    clean_email = req.email.strip().lower()
    user = await db.scalar(select(User).where(func.lower(User.email) == clean_email))
    if not user or user.isDeleted:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not verify_password(req.password, user.passwordHash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    # If baker, check status
    bakery = await db.scalar(select(Bakery).where(Bakery.ownerId == user.id))
    if user.role == Role.BAKER.value and bakery:
        if bakery.isDeleted or bakery.status == BakeryStatus.DELETED.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is no longer active")

    token = create_access_token(data={"sub": user.id, "role": user.role})

    # Set httpOnly cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
    )

    user_dict = {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }
    if bakery:
        user_dict["bakeryId"] = bakery.id
        user_dict["bakerySlug"] = bakery.slug
        user_dict["bakeryStatus"] = bakery.status

    return {"user": user_dict, "token": token}


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterBakerRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    clean_email = req.email.strip().lower()
    # Check email exists (case-insensitive)
    existing_user = await db.scalar(select(User).where(func.lower(User.email) == clean_email))
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered")

    # Create user
    user = User(
        name=req.name.strip(),
        email=clean_email,
        passwordHash=hash_password(req.password),
        phone=req.phone.strip() if req.phone else None,
        role=Role.BAKER.value,
    )
    db.add(user)
    await db.flush()  # To get user.id

    from app.utils.slugify import slugify

    # Create bakery
    base_slug = slugify(req.bakeryName)
    if not base_slug:
        base_slug = "bakery"
    
    slug = base_slug
    counter = 1
    while await db.scalar(select(Bakery).where(Bakery.slug == slug)):
        slug = f"{base_slug}-{counter}"
        counter += 1

    bakery = Bakery(
        ownerId=user.id,
        slug=slug,
        name=req.bakeryName.strip(),
        city=req.city.strip(),
        whatsappNumber=req.whatsappNumber.strip(),
        description=req.description.strip() if req.description else None,
        status=BakeryStatus.PENDING.value,
    )
    db.add(bakery)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(data={"sub": user.id, "role": user.role})

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
    )

    user_dict = {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "bakeryId": bakery.id,
        "bakerySlug": bakery.slug,
        "bakeryStatus": bakery.status,
    }

    return {"user": user_dict, "token": token}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    user_dict = {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
    }
    if current_user.bakery:
        user_dict["bakeryId"] = current_user.bakery.id
        user_dict["bakerySlug"] = current_user.bakery.slug
        user_dict["bakeryStatus"] = current_user.bakery.status
    return user_dict


@router.post("/forgot-password")
async def forgot_password(
    req: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    clean_email = req.email.strip().lower()
    user = await db.scalar(select(User).where(func.lower(User.email) == clean_email))
    if not user or user.isDeleted:
        # Don't reveal if email exists or not
        return {"message": "If an account with that email exists, we sent a password reset link."}

    token = str(uuid.uuid4())
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    
    reset_token = PasswordResetToken(
        email=user.email,
        token=token,
        expiresAt=expires
    )
    db.add(reset_token)
    await db.commit()
    
    settings = get_settings()
    reset_url = f"{settings.frontend_url}/auth/reset-password?token={token}"
    await send_password_reset_email(user.email, reset_url, user.name)
    
    return {
        "message": "If an account with that email exists, we sent a password reset link to your inbox.",
    }


@router.post("/reset-password")
async def reset_password(
    req: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    reset_record = await db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token == req.token)
    )
    
    if not reset_record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    expires_at = reset_record.expiresAt
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
        
    user = await db.scalar(select(User).where(func.lower(User.email) == reset_record.email.lower()))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    user.passwordHash = hash_password(req.password)
    
    await db.delete(reset_record)
    await db.commit()
    
    return {"message": "Password reset successfully. You can now log in."}

