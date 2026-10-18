from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models import Category
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.utils.slugify import slugify

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).order_by(Category.name))
    return result.scalars().all()


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    req: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    base_slug = slugify(req.name)
    if not base_slug:
        base_slug = "category"
        
    slug = base_slug
    counter = 1
    while await db.scalar(select(Category).where(Category.slug == slug)):
        slug = f"{base_slug}-{counter}"
        counter += 1
        
    cat = Category(
        name=req.name.strip(),
        slug=slug,
        icon=req.icon.strip()
    )
    
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    
    return cat


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str,
    req: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    cat = await db.scalar(select(Category).where(Category.id == category_id))
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        
    cat.name = req.name.strip()
    cat.icon = req.icon.strip()
    
    await db.commit()
    await db.refresh(cat)
    
    return cat


@router.delete("/{category_id}")
async def delete_category(
    category_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    cat = await db.scalar(select(Category).where(Category.id == category_id))
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        
    # Check if category is used
    # In Prisma it was cascade delete? Actually we shouldn't delete categories with cakes
    # SQLAlchemy will raise an IntegrityError if we try to delete a category referenced by cakes
    # if we didn't specify cascade="all, delete"
    
    try:
        await db.delete(cat)
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Cannot delete category that is used by cakes."
        )
        
    return {"message": "Category deleted successfully"}
