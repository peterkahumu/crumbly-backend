from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_baker
from app.database import get_db
from app.models import PortfolioItem, User
from app.schemas.portfolio import PortfolioItemCreate, PortfolioItemResponse

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=list[PortfolioItemResponse])
async def list_portfolio_items(
    current_user: User = Depends(require_baker),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.bakery:
        return []

    result = await db.execute(
        select(PortfolioItem)
        .where(PortfolioItem.bakeryId == current_user.bakery.id)
        .order_by(PortfolioItem.createdAt.desc())
    )
    return result.scalars().all()


@router.post("", response_model=PortfolioItemResponse, status_code=status.HTTP_201_CREATED)
async def create_portfolio_item(
    req: PortfolioItemCreate,
    current_user: User = Depends(require_baker),
    db: AsyncSession = Depends(get_db),
):
    item = PortfolioItem(
        bakeryId=current_user.bakery.id,
        imageUrl=req.imageUrl.strip(),
        caption=req.caption.strip() if req.caption else None,
        eventType=req.eventType.strip() if req.eventType else None,
    )
    
    db.add(item)
    await db.commit()
    await db.refresh(item)
    
    return item


@router.delete("/{item_id}")
async def delete_portfolio_item(
    item_id: str,
    current_user: User = Depends(require_baker),
    db: AsyncSession = Depends(get_db),
):
    item = await db.scalar(
        select(PortfolioItem).where(PortfolioItem.id == item_id, PortfolioItem.bakeryId == current_user.bakery.id)
    )
    
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio item not found")
        
    await db.delete(item)
    await db.commit()
    
    return {"message": "Portfolio item deleted"}
