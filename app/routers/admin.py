import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user, require_admin
from app.auth.security import hash_password
from app.config import get_settings
from app.database import get_db
from app.models import Bakery, BakeryStatus, Cake, Category, Order, PasswordResetToken, PortfolioItem, Role, User
from app.schemas.admin import AdminInviteRequest, AdminUserResponse
from app.schemas.bakery import AdminBakeryUpdate
from app.utils.email import send_admin_invitation_email

router = APIRouter(prefix="/admin", tags=["admin"])


def format_bakery_dict(bakery: Bakery, user: User | None = None, cake_count: int = 0, order_count: int = 0):
    owner_dict = None
    email = None
    if user:
        email = user.email
        owner_dict = {"id": user.id, "email": user.email, "name": user.name, "phone": user.phone}
    elif bakery.owner:
        email = bakery.owner.email
        owner_dict = {
            "id": bakery.owner.id,
            "email": bakery.owner.email,
            "name": bakery.owner.name,
            "phone": bakery.owner.phone,
        }

    return {
        "id": bakery.id,
        "name": bakery.name,
        "slug": bakery.slug,
        "city": bakery.city,
        "address": bakery.address,
        "whatsappNumber": bakery.whatsappNumber,
        "mpesaTillNumber": bakery.mpesaTillNumber,
        "description": bakery.description,
        "status": bakery.status,
        "isDeleted": bakery.isDeleted,
        "deletedAt": bakery.deletedAt.isoformat() if bakery.deletedAt else None,
        "createdAt": bakery.createdAt.isoformat() if bakery.createdAt else None,
        "updatedAt": bakery.updatedAt.isoformat() if bakery.updatedAt else None,
        "email": email,
        "owner": owner_dict,
        "_count": {
            "cakes": cake_count,
            "orders": order_count,
        },
    }


@router.get("/bakeries")
async def admin_list_bakeries(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    query = (
        select(
            Bakery,
            User,
            func.count(Cake.id).label("cake_count"),
        )
        .outerjoin(User, Bakery.ownerId == User.id)
        .outerjoin(Cake, Bakery.id == Cake.bakeryId)
        .group_by(Bakery.id, User.id)
        .order_by(desc(Bakery.createdAt))
    )
    result = await db.execute(query)
    rows = result.all()

    bakeries = []
    for bakery, user, cake_count in rows:
        bakeries.append(format_bakery_dict(bakery, user, cake_count=cake_count))

    return bakeries


@router.get("/bakeries/{bakery_id}")
async def admin_get_bakery(
    bakery_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    query = (
        select(Bakery)
        .options(
            selectinload(Bakery.owner),
            selectinload(Bakery.cakes).selectinload(Cake.category),
            selectinload(Bakery.orders),
            selectinload(Bakery.portfolio),
        )
        .where(or_(Bakery.id == bakery_id, Bakery.slug == bakery_id))
    )
    bakery = await db.scalar(query)
    if not bakery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")

    cakes_list = []
    for c in sorted(bakery.cakes or [], key=lambda x: x.createdAt or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        cakes_list.append({
            "id": c.id,
            "bakeryId": c.bakeryId,
            "categoryId": c.categoryId,
            "category": {"name": c.category.name} if c.category else None,
            "name": c.name,
            "slug": c.slug,
            "description": c.description,
            "price": c.price,
            "discountPrice": c.discountPrice,
            "images": c.images or [],
            "sizeOptions": c.sizeOptions,
            "isAvailable": c.isAvailable,
            "isFeatured": c.isFeatured,
            "createdAt": c.createdAt.isoformat() if c.createdAt else None,
        })

    orders_list = []
    for o in sorted(bakery.orders or [], key=lambda x: x.createdAt or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        orders_list.append({
            "id": o.id,
            "bakeryId": o.bakeryId,
            "customerName": o.customerName,
            "customerPhone": o.customerPhone,
            "items": o.items or [],
            "totalAmount": o.totalAmount,
            "status": o.status,
            "channel": o.channel,
            "mpesaReceiptNumber": o.mpesaReceiptNumber,
            "createdAt": o.createdAt.isoformat() if o.createdAt else None,
        })

    portfolio_list = []
    for p in sorted(bakery.portfolio or [], key=lambda x: x.createdAt or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        portfolio_list.append({
            "id": p.id,
            "bakeryId": p.bakeryId,
            "imageUrl": p.imageUrl,
            "caption": p.caption,
            "eventType": p.eventType,
            "createdAt": p.createdAt.isoformat() if p.createdAt else None,
        })

    data = format_bakery_dict(
        bakery,
        bakery.owner,
        cake_count=len(bakery.cakes or []),
        order_count=len(bakery.orders or []),
    )
    data["cakes"] = cakes_list
    data["orders"] = orders_list
    data["portfolio"] = portfolio_list

    return data


@router.patch("/bakeries/{bakery_id}")
async def admin_update_bakery(
    bakery_id: str,
    req: AdminBakeryUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    bakery = await db.scalar(
        select(Bakery).options(selectinload(Bakery.owner)).where(Bakery.id == bakery_id)
    )
    if not bakery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")

    if req.status is not None:
        if req.status not in ["PENDING", "APPROVED", "SUSPENDED", "DELETED"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
        bakery.status = req.status
        if req.status in ["APPROVED", "PENDING", "SUSPENDED"]:
            bakery.isDeleted = False
            bakery.deletedAt = None

    if req.isDeleted is not None:
        bakery.isDeleted = req.isDeleted
        bakery.deletedAt = datetime.now(timezone.utc) if req.isDeleted else None
        if req.isDeleted:
            bakery.status = BakeryStatus.DELETED.value

    if req.name is not None:
        bakery.name = req.name.strip()
    if req.city is not None:
        bakery.city = req.city.strip()
    if req.address is not None:
        bakery.address = req.address.strip() if req.address else None
    if req.whatsappNumber is not None:
        bakery.whatsappNumber = req.whatsappNumber.strip()
    if req.mpesaTillNumber is not None:
        bakery.mpesaTillNumber = req.mpesaTillNumber.strip() if req.mpesaTillNumber else None
    if req.description is not None:
        bakery.description = req.description.strip() if req.description else None

    user = bakery.owner or await db.scalar(select(User).where(User.id == bakery.ownerId))
    if req.email or req.password:
        if user:
            if req.email:
                new_email = req.email.strip().lower()
                existing = await db.scalar(select(User).where(func.lower(User.email) == new_email, User.id != user.id))
                if existing:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")
                user.email = new_email

            if req.password:
                if len(req.password) < 6:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")
                user.passwordHash = hash_password(req.password)

    await db.commit()
    await db.refresh(bakery)

    cake_count = await db.scalar(select(func.count(Cake.id)).where(Cake.bakeryId == bakery.id)) or 0
    return {"bakery": format_bakery_dict(bakery, user, cake_count=cake_count)}


@router.delete("/bakeries/{bakery_id}")
async def admin_delete_bakery(
    bakery_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    bakery = await db.scalar(select(Bakery).where(Bakery.id == bakery_id))
    if not bakery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")

    # Delete cakes
    cakes = await db.scalars(select(Cake).where(Cake.bakeryId == bakery.id))
    for cake in cakes:
        await db.delete(cake)

    bakery.status = BakeryStatus.DELETED.value
    bakery.isDeleted = True
    bakery.deletedAt = datetime.now(timezone.utc)

    user = await db.scalar(select(User).where(User.id == bakery.ownerId))
    if user:
        user.isDeleted = True
        user.deletedAt = datetime.now(timezone.utc)

    await db.commit()

    return {"message": "Bakery archived and cakes removed."}


# ── Admin Invitation & Management

@router.get("/admins", response_model=list[AdminUserResponse])
async def admin_list_admins(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """List all Super Administrators and their invitation/active status."""
    result = await db.scalars(
        select(User)
        .where(User.role == Role.SUPER_ADMIN.value, User.isDeleted.is_(False))
        .order_by(User.createdAt.asc())
    )
    admins = result.all()

    return [
        AdminUserResponse(
            id=u.id,
            name=u.name,
            email=u.email,
            role=u.role,
            createdAt=u.createdAt.isoformat() if u.createdAt else None,
            isPendingInvite=u.passwordHash == "!" or not u.passwordHash,
        )
        for u in admins
    ]


@router.post("/admins/invite")
async def admin_invite_super_admin(
    req: AdminInviteRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Invite another Super Admin to the platform.
    
    Creates a user with an unusable password hash ('!') and sends an invitation
    email with a secure password setup link.
    """
    clean_email = req.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Valid email address is required")

    existing_user = await db.scalar(select(User).where(func.lower(User.email) == clean_email))
    if existing_user and not existing_user.isDeleted:
        # If the user is already a pending invited admin, allow re-inviting / re-sending setup link
        if existing_user.role == Role.SUPER_ADMIN.value and (existing_user.passwordHash == "!" or not existing_user.passwordHash):
            target_user = existing_user
            if req.name and req.name.strip():
                target_user.name = req.name.strip()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists.",
            )
    elif existing_user and existing_user.isDeleted:
        # Reactivate deleted account as pending admin
        existing_user.isDeleted = False
        existing_user.deletedAt = None
        existing_user.role = Role.SUPER_ADMIN.value
        existing_user.passwordHash = "!"
        if req.name and req.name.strip():
            existing_user.name = req.name.strip()
        target_user = existing_user
    else:
        target_user = User(
            name=req.name.strip() if req.name else "Administrator",
            email=clean_email,
            role=Role.SUPER_ADMIN.value,
            passwordHash="!",
        )
        db.add(target_user)

    # Invalidate any old tokens for this email
    old_tokens = await db.scalars(select(PasswordResetToken).where(PasswordResetToken.email == clean_email))
    for ot in old_tokens:
        await db.delete(ot)

    token = str(uuid.uuid4())
    expires = datetime.now(timezone.utc) + timedelta(hours=48)
    reset_token = PasswordResetToken(
        email=clean_email,
        token=token,
        expiresAt=expires,
    )
    db.add(reset_token)
    await db.commit()
    await db.refresh(target_user)

    settings = get_settings()
    setup_url = f"{settings.frontend_url}/auth/reset-password?token={token}"
    email_sent = await send_admin_invitation_email(
        to_email=clean_email,
        setup_url=setup_url,
        recipient_name=target_user.name,
    )

    return {
        "message": f"Invitation successfully sent to {clean_email}.",
        "userId": target_user.id,
        "email": clean_email,
        "name": target_user.name,
        "setupUrl": setup_url,
        "token": token,
        "expiresAt": expires.isoformat(),
        "emailSent": email_sent,
    }


@router.delete("/admins/{admin_id}")
async def admin_delete_super_admin(
    admin_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Soft delete / revoke a Super Administrator account."""
    if current_admin.id == admin_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot revoke your own administrator account.",
        )

    target_user = await db.scalar(
        select(User).where(User.id == admin_id, User.role == Role.SUPER_ADMIN.value)
    )
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Administrator not found")

    target_user.isDeleted = True
    target_user.deletedAt = datetime.now(timezone.utc)
    target_user.passwordHash = "!"
    await db.commit()

    return {"message": f"Administrator {target_user.email} access revoked."}

