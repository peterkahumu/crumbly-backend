from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Bakery, Cake, Role, User
from app.schemas.cake import CakeCreate, CakeResponse, CakeUpdate
from app.utils.slugify import slugify

router = APIRouter(prefix="/cakes", tags=["cakes"])


@router.get("", response_model=list[CakeResponse])
async def list_cakes(
    bakery_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Cake)
        .options(selectinload(Cake.bakery), selectinload(Cake.category))
        .order_by(Cake.createdAt.desc())
    )

    if current_user.role == Role.SUPER_ADMIN.value:
        if bakery_id:
            query = query.where(Cake.bakeryId == bakery_id)
    else:
        if not current_user.bakery:
            return []
        query = query.where(Cake.bakeryId == current_user.bakery.id)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{cake_id}", response_model=CakeResponse)
async def get_cake(
    cake_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Cake)
        .options(selectinload(Cake.bakery), selectinload(Cake.category))
        .where(Cake.id == cake_id)
    )
    if current_user.role != Role.SUPER_ADMIN.value:
        if not current_user.bakery:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")
        query = query.where(Cake.bakeryId == current_user.bakery.id)

    cake = await db.scalar(query)
    if not cake:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cake not found")

    return cake


@router.post("", response_model=CakeResponse, status_code=status.HTTP_201_CREATED)
async def create_cake(
    req: CakeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != Role.BAKER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only bakers can create cakes")

    bakery = current_user.bakery
    if not bakery:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No bakery associated with account")

    # Generate slug scoped to bakery
    base_slug = slugify(req.name)
    if not base_slug:
        base_slug = "cake"

    slug = base_slug
    counter = 1
    while await db.scalar(select(Cake).where(Cake.bakeryId == bakery.id, Cake.slug == slug)):
        slug = f"{base_slug}-{counter}"
        counter += 1

    size_options = [opt.model_dump() for opt in req.sizeOptions] if req.sizeOptions else None

    cake = Cake(
        bakeryId=bakery.id,
        categoryId=req.categoryId,
        name=req.name.strip(),
        slug=slug,
        description=req.description.strip() if req.description else None,
        price=req.price,
        discountPrice=req.discountPrice,
        images=req.images,
        sizeOptions=size_options,
        isAvailable=req.isAvailable,
        isFeatured=req.isFeatured,
    )

    db.add(cake)
    await db.commit()
    await db.refresh(cake)
    cake.bakery = bakery

    return cake


@router.put("/{cake_id}", response_model=CakeResponse)
async def update_cake(
    cake_id: str,
    req: CakeUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Cake).options(selectinload(Cake.bakery), selectinload(Cake.category)).where(Cake.id == cake_id)
    if current_user.role != Role.SUPER_ADMIN.value:
        if not current_user.bakery:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")
        query = query.where(Cake.bakeryId == current_user.bakery.id)

    cake = await db.scalar(query)
    if not cake:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cake not found")

    if req.name is not None:
        cake.name = req.name.strip()
    if req.categoryId is not None:
        cake.categoryId = req.categoryId
    if req.description is not None:
        cake.description = req.description.strip() if req.description else None
    if req.price is not None:
        cake.price = req.price
    if req.discountPrice is not None:
        cake.discountPrice = req.discountPrice
    if req.images is not None:
        cake.images = req.images
    if req.sizeOptions is not None:
        cake.sizeOptions = [opt.model_dump() for opt in req.sizeOptions]
    if req.isAvailable is not None:
        cake.isAvailable = req.isAvailable
    if req.isFeatured is not None:
        cake.isFeatured = req.isFeatured

    await db.commit()
    await db.refresh(cake)

    return cake


@router.delete("/{cake_id}")
async def delete_cake(
    cake_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Cake).where(Cake.id == cake_id)
    if current_user.role != Role.SUPER_ADMIN.value:
        if not current_user.bakery:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")
        query = query.where(Cake.bakeryId == current_user.bakery.id)

    cake = await db.scalar(query)
    if not cake:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cake not found")

    await db.delete(cake)
    await db.commit()

    return {"message": "Cake deleted successfully"}

