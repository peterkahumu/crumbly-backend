from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Bakery, Cake, Category, PortfolioItem
from app.schemas.bakery import BakeryListItem, BakeryResponse
from app.schemas.cake import CakeResponse
from app.schemas.category import CategoryResponse
from app.schemas.portfolio import PortfolioItemResponse

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/home")
async def get_home_data(db: AsyncSession = Depends(get_db)):
    """Data for the home page (categories, featured cakes, bakeries)."""
    # Categories
    categories_result = await db.execute(select(Category).order_by(Category.name))
    categories = categories_result.scalars().all()
    
    # Featured cakes
    cakes_result = await db.execute(
        select(Cake)
        .options(selectinload(Cake.bakery), selectinload(Cake.category))
        .where(Cake.isFeatured == True, Cake.isAvailable == True)
        .join(Cake.bakery)
        .where(Bakery.status == "APPROVED", Bakery.isDeleted == False)
        .order_by(desc(Cake.createdAt))
        .limit(12)
    )
    featured_cakes = list(cakes_result.scalars().all())
    if len(featured_cakes) < 6:
        existing_ids = [c.id for c in featured_cakes]
        supp_stmt = (
            select(Cake)
            .options(selectinload(Cake.bakery), selectinload(Cake.category))
            .join(Cake.bakery)
            .where(Cake.isAvailable == True, Bakery.status == "APPROVED", Bakery.isDeleted == False)
        )
        if existing_ids:
            supp_stmt = supp_stmt.where(~Cake.id.in_(existing_ids))
        supp_stmt = supp_stmt.order_by(desc(Cake.createdAt)).limit(12 - len(featured_cakes))
        supp_res = await db.execute(supp_stmt)
        featured_cakes.extend(supp_res.scalars().all())
    
    # Bakeries: Show all approved bakeries (up to 24), newest first so new bakeries appear
    bakeries_result = await db.execute(
        select(Bakery, func.count(Cake.id).label("cake_count"))
        .outerjoin(Cake, Bakery.id == Cake.bakeryId)
        .where(Bakery.status == "APPROVED", Bakery.isDeleted == False)
        .group_by(Bakery.id)
        .order_by(desc(Bakery.createdAt))
        .limit(24)
    )
    bakeries_data = bakeries_result.all()
    bakeries = []
    for bakery, count in bakeries_data:
        b_dict = BakeryListItem.model_validate(bakery).model_dump()
        b_dict["cake_count"] = count
        b_dict["_count"] = {"cakes": count}
        bakeries.append(b_dict)
        
    return {
        "categories": [CategoryResponse.model_validate(c).model_dump() for c in categories],
        "featuredCakes": [CakeResponse.model_validate(c).model_dump() for c in featured_cakes],
        "bakeries": bakeries
    }


@router.get("/cakes")
async def list_public_cakes(
    category: str | None = None,
    city: str | None = None,
    search: str | None = None,
    sort: str = "newest",
    min_price: int | None = None,
    max_price: int | None = None,
    page: int = 1,
    page_size: int = 24,
    db: AsyncSession = Depends(get_db),
):
    # Base query for available cakes from approved, active bakeries
    query = (
        select(Cake)
        .options(selectinload(Cake.bakery), selectinload(Cake.category))
        .join(Bakery, Cake.bakeryId == Bakery.id)
        .where(Cake.isAvailable == True, Bakery.status == "APPROVED", Bakery.isDeleted == False)
    )

    if category and category != "all":
        query = query.join(Category, Cake.categoryId == Category.id).where(Category.slug == category)

    if city and city != "all":
        query = query.where(Bakery.city == city)

    if search and search.strip():
        s = f"%{search.strip().lower()}%"
        query = query.where(or_(func.lower(Cake.name).like(s), func.lower(Cake.description).like(s)))

    if min_price is not None:
        query = query.where(Cake.price >= min_price)
    if max_price is not None:
        query = query.where(Cake.price <= max_price)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_count = await db.scalar(count_query) or 0

    # Sort
    if sort == "price_asc":
        query = query.order_by(Cake.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Cake.price.desc())
    else:
        query = query.order_by(Cake.createdAt.desc())

    # Pagination
    offset = (max(1, page) - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    cakes = result.scalars().all()

    # Price bounds
    bounds_result = await db.execute(
        select(func.min(Cake.price), func.max(Cake.price))
        .join(Bakery, Cake.bakeryId == Bakery.id)
        .where(Cake.isAvailable == True, Bakery.status == "APPROVED", Bakery.isDeleted == False)
    )
    min_p, max_p = bounds_result.first()

    # Available cities
    cities_result = await db.execute(
        select(Bakery.city)
        .where(Bakery.status == "APPROVED", Bakery.isDeleted == False)
        .distinct()
    )
    cities = sorted([c for c in cities_result.scalars().all() if c])

    # Available categories
    cats_result = await db.execute(select(Category).order_by(Category.name.asc()))
    categories = cats_result.scalars().all()

    cakes_list = []
    for c in cakes:
        c_dict = CakeResponse.model_validate(c).model_dump()
        if c.bakery:
            c_dict["bakery"] = {"name": c.bakery.name, "slug": c.bakery.slug}
        cakes_list.append(c_dict)

    return {
        "cakes": cakes_list,
        "totalCount": total_count,
        "page": page,
        "pageSize": page_size,
        "totalPages": (total_count + page_size - 1) // page_size if total_count else 1,
        "priceRange": {"min": min_p or 0, "max": max_p or 0},
        "cities": cities,
        "categories": [CategoryResponse.model_validate(c).model_dump() for c in categories],
        "filters": {
            "category": category,
            "q": search,
            "city": city,
            "sort": sort,
            "minPrice": min_price,
            "maxPrice": max_price,
        },
    }


@router.get("/bakeries")
async def list_public_bakeries(
    city: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Bakery, func.count(Cake.id).label("cake_count"))
        .outerjoin(Cake, Bakery.id == Cake.bakeryId)
        .where(Bakery.status == "APPROVED", Bakery.isDeleted == False)
        .group_by(Bakery.id)
        .order_by(Bakery.createdAt.desc())
    )

    if city and city != "all":
        query = query.where(Bakery.city == city)

    result = await db.execute(query)
    data = result.all()

    bakeries = []
    for bakery, count in data:
        b_dict = BakeryListItem.model_validate(bakery).model_dump()
        b_dict["cake_count"] = count
        b_dict["_count"] = {"cakes": count}
        bakeries.append(b_dict)

    cities_result = await db.execute(
        select(Bakery.city)
        .where(Bakery.status == "APPROVED", Bakery.isDeleted == False)
        .distinct()
    )
    cities = sorted([c for c in cities_result.scalars().all() if c])

    return {
        "bakeries": bakeries,
        "cities": cities,
        "filters": {"city": city},
    }


@router.get("/bakery/{slug}")
async def get_public_bakery(
    slug: str,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    bakery = await db.scalar(
        select(Bakery)
        .where(Bakery.slug == slug, Bakery.status == "APPROVED", Bakery.isDeleted == False)
    )

    if not bakery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")

    # Categories for this bakery
    cat_query = (
        select(Category)
        .join(Cake, Cake.categoryId == Category.id)
        .where(Cake.bakeryId == bakery.id)
        .distinct()
        .order_by(Category.name)
    )
    cats_res = await db.execute(cat_query)
    categories = cats_res.scalars().all()

    # Cakes for this bakery
    cake_query = (
        select(Cake)
        .options(selectinload(Cake.category), selectinload(Cake.bakery))
        .where(Cake.bakeryId == bakery.id, Cake.isAvailable == True)
        .order_by(Cake.createdAt.desc())
    )
    if category and category != "all":
        cake_query = cake_query.join(Category, Cake.categoryId == Category.id).where(Category.slug == category)

    cakes_result = await db.execute(cake_query)
    cakes = cakes_result.scalars().all()

    cakes_list = [CakeResponse.model_validate(c).model_dump() for c in cakes]

    return {
        "bakery": BakeryResponse.model_validate(bakery).model_dump(),
        "categories": [CategoryResponse.model_validate(c).model_dump() for c in categories],
        "cakes": cakes_list,
        "filters": {"category": category},
    }


@router.get("/bakery/{slug}/cakes/{cake_slug}")
async def get_public_cake(slug: str, cake_slug: str, db: AsyncSession = Depends(get_db)):
    bakery = await db.scalar(
        select(Bakery)
        .where(Bakery.slug == slug, Bakery.status == "APPROVED", Bakery.isDeleted == False)
    )
    if not bakery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")

    cake = await db.scalar(
        select(Cake)
        .options(selectinload(Cake.category), selectinload(Cake.bakery))
        .where(Cake.bakeryId == bakery.id, Cake.slug == cake_slug, Cake.isAvailable == True)
    )

    if not cake:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cake not found")

    similar_result = await db.execute(
        select(Cake)
        .options(selectinload(Cake.category), selectinload(Cake.bakery))
        .where(
            Cake.bakeryId == bakery.id,
            Cake.categoryId == cake.categoryId,
            Cake.id != cake.id,
            Cake.isAvailable == True,
        )
        .limit(4)
    )
    similar_cakes = similar_result.scalars().all()

    return {
        "cake": CakeResponse.model_validate(cake).model_dump(),
        "bakery": BakeryResponse.model_validate(bakery).model_dump(),
        "similarCakes": [CakeResponse.model_validate(c).model_dump() for c in similar_cakes],
    }


@router.get("/bakery/{slug}/portfolio")
async def get_public_portfolio(slug: str, db: AsyncSession = Depends(get_db)):
    bakery = await db.scalar(
        select(Bakery)
        .where(Bakery.slug == slug, Bakery.status == "APPROVED", Bakery.isDeleted == False)
    )
    if not bakery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")

    portfolio_result = await db.execute(
        select(PortfolioItem)
        .where(PortfolioItem.bakeryId == bakery.id)
        .order_by(PortfolioItem.createdAt.desc())
    )
    portfolio = portfolio_result.scalars().all()

    return {
        "bakery": BakeryResponse.model_validate(bakery).model_dump(),
        "portfolio": [PortfolioItemResponse.model_validate(p).model_dump() for p in portfolio],
    }

