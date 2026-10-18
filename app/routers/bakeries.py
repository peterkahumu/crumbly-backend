from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_baker
from app.auth.security import hash_password
from app.database import get_db
from app.models import User
from app.schemas.bakery import BakeryResponse, BakerySettingsUpdate

router = APIRouter(prefix="/bakeries", tags=["bakeries"])


@router.get("/me", response_model=BakeryResponse)
async def get_my_bakery(
    current_user: User = Depends(require_baker),
):
    bakery = current_user.bakery
    if not bakery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")
    return bakery


@router.put("/me", response_model=BakeryResponse)
async def update_my_bakery(
    req: BakerySettingsUpdate,
    current_user: User = Depends(require_baker),
    db: AsyncSession = Depends(get_db),
):
    bakery = current_user.bakery
    if not bakery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")

    # Update bakery fields
    bakery.name = req.name.strip()
    bakery.description = req.description.strip() if req.description else None
    bakery.city = req.city.strip()
    bakery.address = req.address.strip() if req.address else None
    bakery.whatsappNumber = req.whatsappNumber.strip()
    bakery.mpesaTillNumber = req.mpesaTillNumber.strip() if req.mpesaTillNumber else None
    
    if req.logoUrl is not None:
        bakery.logoUrl = req.logoUrl if req.logoUrl.strip() else None
        
    if req.coverImageUrl is not None:
        bakery.coverImageUrl = req.coverImageUrl if req.coverImageUrl.strip() else None

    # Update user password if provided
    if req.newPassword:
        if len(req.newPassword) < 6:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")
        current_user.passwordHash = hash_password(req.newPassword)

    await db.commit()
    await db.refresh(bakery)

    return bakery
