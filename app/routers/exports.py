from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user, require_admin, require_baker
from app.database import get_db
from app.models import Bakery, Cake, Order, OrderStatus, PortfolioItem, Review, Role, User
from app.utils.exports import (
    build_analytics_csv,
    build_analytics_pdf,
    build_analytics_workbook,
    export_to_csv,
    export_to_excel,
    export_to_pdf,
)

router = APIRouter(tags=["exports"])

ExportFormat = Literal["csv", "excel", "xlsx", "pdf"]


def get_response(io_data, filename: str, format: str):
    fmt = format.lower().strip()
    if fmt in ("xlsx", "excel"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    elif fmt == "pdf":
        media_type = "application/pdf"
        ext = "pdf"
    elif fmt == "csv":
        media_type = "text/csv; charset=utf-8"
        ext = "csv"
    else:
        raise HTTPException(status_code=400, detail="Unsupported format. Use xlsx, pdf, or csv.")

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}.{ext}"',
        "Cache-Control": "private, no-store",
    }

    return StreamingResponse(io_data, media_type=media_type, headers=headers)


def parse_date_filters(range_val: str | None, from_val: str | None, to_val: str | None):
    now = datetime.now(timezone.utc)
    today = datetime(now.year, now.month, now.day, 23, 59, 59, 999999, tzinfo=timezone.utc)

    range_days = {
        "7d": 7,
        "30d": 30,
        "90d": 90,
        "6m": 182,
        "12m": 365,
    }

    from_dt = None
    to_dt = today
    label = "Last 30 days"

    if range_val == "all":
        from_dt = None
        label = "All time"
    elif range_val == "custom" and from_val:
        try:
            p_from = datetime.strptime(from_val[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            p_to = (
                datetime.strptime(to_val[:10], "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc
                )
                if to_val
                else today
            )
            if p_from > p_to:
                p_from, p_to = p_to, p_from
            from_dt = p_from
            to_dt = p_to
            label = f"{p_from.strftime('%b %d, %Y')} – {p_to.strftime('%b %d, %Y')}"
        except Exception:
            from_dt = today - timedelta(days=29)
            from_dt = from_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            label = "Last 30 days"
    elif range_val in range_days:
        days = range_days[range_val]
        from_dt = today - timedelta(days=days - 1)
        from_dt = from_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        label = (
            f"Last {days} days"
            if "d" in range_val
            else f"Last {range_val[0]} months"
            if "m" in range_val
            else f"Last {days} days"
        )
    else:
        # Default 30 days
        from_dt = today - timedelta(days=29)
        from_dt = from_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        label = "Last 30 days"

    date_range_str = (
        f"{from_dt.strftime('%b %d, %Y')} – {to_dt.strftime('%b %d, %Y')}" if from_dt else "All time on record"
    )

    return from_dt, to_dt, label, date_range_str


# ──────────────────────────────────────────────── Baker Stats Export


@router.get("/analytics/export")
@router.get("/exports/analytics")
async def export_baker_stats(
    format: str = Query("xlsx", description="Format to export (xlsx, pdf, csv)"),
    range: str | None = Query("30d", description="Predefined range preset (7d, 30d, 90d, 6m, 12m, all, custom)"),
    from_date: str | None = Query(None, alias="from", description="Custom range start date (YYYY-MM-DD)"),
    to_date: str | None = Query(None, alias="to", description="Custom range end date (YYYY-MM-DD)"),
    current_user: User = Depends(require_baker),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.bakery:
        raise HTTPException(status_code=400, detail="User has no bakery")

    bakery = current_user.bakery
    if bakery.isDeleted or bakery.status == "DELETED":
        raise HTTPException(status_code=403, detail="Account is no longer active")
    if bakery.status == "SUSPENDED":
        raise HTTPException(status_code=403, detail="Bakery suspended")

    from_dt, to_dt, period_label, date_range_str = parse_date_filters(range, from_date, to_date)

    # 1. Orders
    order_stmt = select(Order).where(Order.bakeryId == bakery.id)
    if from_dt:
        order_stmt = order_stmt.where(Order.createdAt >= from_dt)
    if to_dt:
        order_stmt = order_stmt.where(Order.createdAt <= to_dt)
    order_stmt = order_stmt.order_by(Order.createdAt.desc())
    orders = (await db.execute(order_stmt)).scalars().all()

    # 2. Cakes
    cake_stmt = select(Cake).options(selectinload(Cake.category)).where(Cake.bakeryId == bakery.id)
    cakes = (await db.execute(cake_stmt)).scalars().all()

    # 3. Portfolio
    portfolio_stmt = select(PortfolioItem).where(PortfolioItem.bakeryId == bakery.id)
    portfolio_items = (await db.execute(portfolio_stmt)).scalars().all()

    # 4. Reviews
    review_stmt = select(Review).where(Review.bakeryId == bakery.id)
    if from_dt:
        review_stmt = review_stmt.where(Review.createdAt >= from_dt)
    if to_dt:
        review_stmt = review_stmt.where(Review.createdAt <= to_dt)
    reviews = (await db.execute(review_stmt)).scalars().all()

    # Aggregations
    total_orders = len(orders)
    revenue = sum(o.totalAmount for o in orders if o.status != OrderStatus.CANCELLED.value)
    avg_order_value = round(revenue / total_orders) if total_orders else 0

    status_counts = {s.value: 0 for s in OrderStatus}
    for o in orders:
        status_counts[o.status] = status_counts.get(o.status, 0) + 1

    completed_orders = status_counts.get(OrderStatus.COMPLETED.value, 0)
    completion_rate = round((completed_orders / total_orders) * 100) if total_orders else 0

    total_cakes = len(cakes)
    available_cakes = sum(1 for c in cakes if c.isAvailable)
    featured_cakes = sum(1 for c in cakes if c.isFeatured)
    discounted_cakes = sum(1 for c in cakes if c.discountPrice is not None)
    portfolio_count = len(portfolio_items)

    total_reviews = len(reviews)
    avg_rating = round(sum(r.rating for r in reviews) / total_reviews, 1) if total_reviews else None

    # Channels
    wa_orders = [o for o in orders if o.channel == "WHATSAPP"]
    mp_orders = [o for o in orders if o.channel == "MPESA"]
    wa_rev = sum(o.totalAmount for o in wa_orders if o.status != OrderStatus.CANCELLED.value)
    mp_rev = sum(o.totalAmount for o in mp_orders if o.status != OrderStatus.CANCELLED.value)

    # Revenue Trend (daily)
    daily_trend_map = {}
    for o in orders:
        if o.createdAt:
            day_key = o.createdAt.strftime("%Y-%m-%d")
            daily_trend_map.setdefault(day_key, {"orders": 0, "revenue": 0})
            daily_trend_map[day_key]["orders"] += 1
            if o.status != OrderStatus.CANCELLED.value:
                daily_trend_map[day_key]["revenue"] += o.totalAmount

    trend_rows = [
        [day, daily_trend_map[day]["orders"], daily_trend_map[day]["revenue"]]
        for day in sorted(daily_trend_map.keys())
    ]

    # Top Cakes
    cake_cat_map = {c.id: c.category.name if c.category else "Uncategorised" for c in cakes}
    cake_sales = {}
    for o in orders:
        if isinstance(o.items, list):
            for item in o.items:
                c_name = item.get("name", "Unknown Cake")
                qty = int(item.get("qty", 1) or 1)
                price = int(item.get("price", 0) or 0)
                cid = item.get("cakeId")
                cat = cake_cat_map.get(cid, "Uncategorised")
                if c_name not in cake_sales:
                    cake_sales[c_name] = {"category": cat, "qty": 0, "revenue": 0}
                cake_sales[c_name]["qty"] += qty
                cake_sales[c_name]["revenue"] += qty * price

    top_cakes_sorted = sorted(cake_sales.items(), key=lambda x: x[1]["revenue"], reverse=True)
    top_cakes_rows = [
        [name, data["category"], data["qty"], data["revenue"]] for name, data in top_cakes_sorted
    ]

    # Category Supply & Demand
    cat_supply = {}
    for c in cakes:
        cat_name = c.category.name if c.category else "Uncategorised"
        cat_supply[cat_name] = cat_supply.get(cat_name, 0) + 1

    cat_demand = {}
    for data in cake_sales.values():
        cat_name = data["category"]
        cat_demand[cat_name] = cat_demand.get(cat_name, 0) + data["qty"]

    categories_rows = [
        [cat, cat_supply.get(cat, 0), cat_demand.get(cat, 0)]
        for cat in sorted(set(list(cat_supply.keys()) + list(cat_demand.keys())))
    ]

    # Portfolio Mix
    portfolio_mix = {}
    for p in portfolio_items:
        evt = p.eventType or "Unlabelled"
        portfolio_mix[evt] = portfolio_mix.get(evt, 0) + 1
    portfolio_rows = [[evt, count] for evt, count in sorted(portfolio_mix.items(), key=lambda x: x[1], reverse=True)]

    # Ratings Breakdown
    rating_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for r in reviews:
        if r.rating in rating_counts:
            rating_counts[r.rating] += 1
    ratings_rows = [[f"{star} Stars", rating_counts[star]] for star in [5, 4, 3, 2, 1]]

    # Assemble Report Structure
    report_data = {
        "title": bakery.name,
        "subtitle": "Bakery Performance Report",
        "scope": "baker",
        "period_label": period_label,
        "date_range": date_range_str,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "filters": [("Bakery", bakery.name)],
        "kpis": [
            {"label": "Revenue", "value": f"KES {revenue:,.0f}"},
            {"label": "Orders", "value": f"{total_orders:,}"},
            {"label": "Average Order", "value": f"KES {avg_order_value:,.0f}"},
            {"label": "Completion Rate", "value": f"{completion_rate}%"},
            {"label": "Cakes Listed", "value": f"{total_cakes:,}"},
            {"label": "Customer Reviews", "value": f"{total_reviews:,} ({avg_rating or '—'} / 5)"},
        ],
        "sheets": [
            {
                "name": "Summary",
                "columns": ["Metric", "Value"],
                "rows": [
                    ["Reporting Period", period_label],
                    ["Date Range", date_range_str],
                    ["Bakery Name", bakery.name],
                    ["City", bakery.city],
                    ["Total Orders", total_orders],
                    ["Total Revenue", f"KES {revenue:,.0f}"],
                    ["Average Order Value", f"KES {avg_order_value:,.0f}"],
                    ["Completion Rate", f"{completion_rate}%"],
                    ["Cakes Listed", total_cakes],
                    ["Cakes Available", available_cakes],
                    ["Cakes Featured", featured_cakes],
                    ["Cakes Discounted", discounted_cakes],
                    ["Portfolio Photos", portfolio_count],
                    ["Total Reviews", total_reviews],
                    ["Average Rating", f"{avg_rating or 'No reviews'} / 5"],
                ],
            },
            {
                "name": "Revenue Trend",
                "columns": ["Date", "Orders", "Revenue (KES)"],
                "money_cols": [2],
                "rows": trend_rows,
            },
            {
                "name": "Order Workflow",
                "columns": ["Stage", "Orders Count", "Share of Total"],
                "rows": [
                    [
                        "Pending",
                        status_counts["PENDING"],
                        f"{(status_counts['PENDING'] / total_orders * 100):.1f}%" if total_orders else "0.0%",
                    ],
                    [
                        "Contacted",
                        status_counts["CONTACTED"],
                        f"{(status_counts['CONTACTED'] / total_orders * 100):.1f}%" if total_orders else "0.0%",
                    ],
                    [
                        "Confirmed",
                        status_counts["CONFIRMED"],
                        f"{(status_counts['CONFIRMED'] / total_orders * 100):.1f}%" if total_orders else "0.0%",
                    ],
                    [
                        "Completed",
                        status_counts["COMPLETED"],
                        f"{(status_counts['COMPLETED'] / total_orders * 100):.1f}%" if total_orders else "0.0%",
                    ],
                    [
                        "Cancelled",
                        status_counts["CANCELLED"],
                        f"{(status_counts['CANCELLED'] / total_orders * 100):.1f}%" if total_orders else "0.0%",
                    ],
                ],
            },
            {
                "name": "Channels",
                "columns": ["Channel", "Orders", "Revenue (KES)"],
                "money_cols": [2],
                "rows": [
                    ["WhatsApp", len(wa_orders), wa_rev],
                    ["M-Pesa", len(mp_orders), mp_rev],
                ],
            },
            {
                "name": "Top Cakes",
                "columns": ["Cake Name", "Category", "Units Sold", "Revenue (KES)"],
                "money_cols": [3],
                "rows": top_cakes_rows,
            },
            {
                "name": "Categories",
                "columns": ["Category", "Cakes Listed", "Units Ordered"],
                "rows": categories_rows,
            },
            {
                "name": "Portfolio",
                "columns": ["Event Type", "Photos Count"],
                "rows": portfolio_rows,
            },
            {
                "name": "Customer Ratings",
                "columns": ["Star Rating", "Reviews Count"],
                "rows": ratings_rows,
            },
        ],
    }

    # Generate output
    fmt = format.lower().strip()
    from_stamp = from_dt.strftime("%Y-%m-%d") if from_dt else "all"
    to_stamp = to_dt.strftime("%Y-%m-%d")
    filename = f"crumbly-baker-analytics-{from_stamp}_{to_stamp}"

    if fmt in ("xlsx", "excel"):
        io_data = build_analytics_workbook(report_data)
    elif fmt == "pdf":
        io_data = build_analytics_pdf(report_data)
    elif fmt == "csv":
        io_data = build_analytics_csv(report_data)
    else:
        raise HTTPException(status_code=400, detail="Unsupported format. Use xlsx, pdf, or csv.")

    return get_response(io_data, filename, fmt)


# ──────────────────────────────────────────────── Admin / Platform Stats Export


@router.get("/admin/analytics/export")
@router.get("/exports/admin/analytics")
async def export_admin_stats(
    format: str = Query("xlsx", description="Format to export (xlsx, pdf, csv)"),
    range: str | None = Query("30d", description="Predefined range preset (7d, 30d, 90d, 6m, 12m, all, custom)"),
    from_date: str | None = Query(None, alias="from", description="Custom range start date (YYYY-MM-DD)"),
    to_date: str | None = Query(None, alias="to", description="Custom range end date (YYYY-MM-DD)"),
    city: str | None = Query(None, description="Filter by city"),
    bakery: str | None = Query(None, description="Filter by bakery ID"),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from_dt, to_dt, period_label, date_range_str = parse_date_filters(range, from_date, to_date)

    # 1. Bakeries
    bakery_stmt = select(Bakery).where(Bakery.isDeleted == False)
    if city:
        bakery_stmt = bakery_stmt.where(Bakery.city == city)
    if bakery:
        bakery_stmt = bakery_stmt.where(Bakery.id == bakery)
    bakeries = (await db.execute(bakery_stmt)).scalars().all()
    bakery_map = {b.id: b for b in bakeries}
    scoped_bakery_ids = list(bakery_map.keys())

    filter_summary = []
    if city:
        filter_summary.append(("City", city))
    if bakery and bakery in bakery_map:
        filter_summary.append(("Bakery", bakery_map[bakery].name))

    # 2. Orders
    order_stmt = select(Order).options(selectinload(Order.bakery))
    if scoped_bakery_ids:
        order_stmt = order_stmt.where(Order.bakeryId.in_(scoped_bakery_ids))
    elif bakery or city:
        # User filtered by non-existent city or bakery
        order_stmt = order_stmt.where(False)

    if from_dt:
        order_stmt = order_stmt.where(Order.createdAt >= from_dt)
    if to_dt:
        order_stmt = order_stmt.where(Order.createdAt <= to_dt)
    order_stmt = order_stmt.order_by(Order.createdAt.desc())
    orders = (await db.execute(order_stmt)).scalars().all()

    # 3. Cakes
    cake_stmt = select(Cake).options(selectinload(Cake.category), selectinload(Cake.bakery))
    if scoped_bakery_ids:
        cake_stmt = cake_stmt.where(Cake.bakeryId.in_(scoped_bakery_ids))
    elif bakery or city:
        cake_stmt = cake_stmt.where(False)
    cakes = (await db.execute(cake_stmt)).scalars().all()

    # 4. Reviews
    review_stmt = select(Review)
    if scoped_bakery_ids:
        review_stmt = review_stmt.where(Review.bakeryId.in_(scoped_bakery_ids))
    elif bakery or city:
        review_stmt = review_stmt.where(False)
    if from_dt:
        review_stmt = review_stmt.where(Review.createdAt >= from_dt)
    if to_dt:
        review_stmt = review_stmt.where(Review.createdAt <= to_dt)
    reviews = (await db.execute(review_stmt)).scalars().all()

    # Aggregations
    total_orders = len(orders)
    revenue = sum(o.totalAmount for o in orders if o.status != OrderStatus.CANCELLED.value)
    avg_order_value = round(revenue / total_orders) if total_orders else 0

    status_counts = {s.value: 0 for s in OrderStatus}
    for o in orders:
        status_counts[o.status] = status_counts.get(o.status, 0) + 1

    completed_orders = status_counts.get(OrderStatus.COMPLETED.value, 0)
    completion_rate = round((completed_orders / total_orders) * 100) if total_orders else 0

    total_bakeries = len(bakeries)
    approved_bakeries = sum(1 for b in bakeries if b.status == "APPROVED")
    pending_bakeries = sum(1 for b in bakeries if b.status == "PENDING")
    suspended_bakeries = sum(1 for b in bakeries if b.status == "SUSPENDED")

    total_cakes = len(cakes)
    avg_cake_price = round(sum(c.price for c in cakes) / total_cakes) if total_cakes else 0
    cities_covered = len(set(b.city for b in bakeries if b.city))

    total_reviews = len(reviews)
    avg_rating = round(sum(r.rating for r in reviews) / total_reviews, 1) if total_reviews else None

    # Channels
    wa_orders = [o for o in orders if o.channel == "WHATSAPP"]
    mp_orders = [o for o in orders if o.channel == "MPESA"]
    wa_rev = sum(o.totalAmount for o in wa_orders if o.status != OrderStatus.CANCELLED.value)
    mp_rev = sum(o.totalAmount for o in mp_orders if o.status != OrderStatus.CANCELLED.value)

    # Daily Trend
    daily_trend_map = {}
    for o in orders:
        if o.createdAt:
            day_key = o.createdAt.strftime("%Y-%m-%d")
            daily_trend_map.setdefault(day_key, {"orders": 0, "revenue": 0})
            daily_trend_map[day_key]["orders"] += 1
            if o.status != OrderStatus.CANCELLED.value:
                daily_trend_map[day_key]["revenue"] += o.totalAmount

    trend_rows = [
        [day, daily_trend_map[day]["orders"], daily_trend_map[day]["revenue"]]
        for day in sorted(daily_trend_map.keys())
    ]

    # Top Bakeries Leaderboard
    bakery_sales = {}
    for o in orders:
        b_id = o.bakeryId
        bakery_sales.setdefault(b_id, {"orders": 0, "revenue": 0})
        bakery_sales[b_id]["orders"] += 1
        if o.status != OrderStatus.CANCELLED.value:
            bakery_sales[b_id]["revenue"] += o.totalAmount

    leaderboard_rows = []
    for b_id, sales in sorted(bakery_sales.items(), key=lambda x: x[1]["revenue"], reverse=True):
        b_obj = bakery_map.get(b_id)
        b_name = b_obj.name if b_obj else (orders[0].bakery.name if orders and orders[0].bakery else "Removed Bakery")
        b_city = b_obj.city if b_obj else "—"
        leaderboard_rows.append([b_name, b_city, sales["orders"], sales["revenue"]])

    # Cities Breakdown
    city_map = {}
    cake_counts_by_bakery = {}
    for c in cakes:
        cake_counts_by_bakery[c.bakeryId] = cake_counts_by_bakery.get(c.bakeryId, 0) + 1

    for b in bakeries:
        city_name = b.city or "Unknown"
        city_map.setdefault(city_name, {"bakeries": 0, "approved": 0, "cakes": 0})
        city_map[city_name]["bakeries"] += 1
        if b.status == "APPROVED":
            city_map[city_name]["approved"] += 1
        city_map[city_name]["cakes"] += cake_counts_by_bakery.get(b.id, 0)

    cities_rows = [
        [c_name, data["bakeries"], data["approved"], data["cakes"]]
        for c_name, data in sorted(city_map.items(), key=lambda x: x[1]["bakeries"], reverse=True)
    ]

    # Top Cakes across platform
    cake_cat_map = {c.id: (c.category.name if c.category else "Uncategorised", c.bakery.name if c.bakery else "—") for c in cakes}
    cake_sales = {}
    for o in orders:
        if isinstance(o.items, list):
            for item in o.items:
                c_name = item.get("name", "Unknown Cake")
                qty = int(item.get("qty", 1) or 1)
                price = int(item.get("price", 0) or 0)
                cid = item.get("cakeId")
                cat_info = cake_cat_map.get(cid, ("Uncategorised", "—"))
                if c_name not in cake_sales:
                    cake_sales[c_name] = {"category": cat_info[0], "bakery": cat_info[1], "qty": 0, "revenue": 0}
                cake_sales[c_name]["qty"] += qty
                cake_sales[c_name]["revenue"] += qty * price

    top_cakes_sorted = sorted(cake_sales.items(), key=lambda x: x[1]["revenue"], reverse=True)
    top_cakes_rows = [
        [name, data["bakery"], data["qty"], data["revenue"]] for name, data in top_cakes_sorted[:30]
    ]

    # Recent Orders (up to 30)
    recent_orders_rows = []
    for o in orders[:30]:
        recent_orders_rows.append(
            [
                o.createdAt.strftime("%Y-%m-%d %H:%M") if o.createdAt else "—",
                o.bakery.name if o.bakery else "—",
                o.customerName,
                o.customerPhone,
                "WhatsApp" if o.channel == "WHATSAPP" else "M-Pesa",
                o.status,
                o.totalAmount,
            ]
        )

    # Ratings Breakdown
    rating_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for r in reviews:
        if r.rating in rating_counts:
            rating_counts[r.rating] += 1
    ratings_rows = [[f"{star} Stars", rating_counts[star]] for star in [5, 4, 3, 2, 1]]

    # Assemble Report Structure
    report_data = {
        "title": "Crumbly Marketplace",
        "subtitle": "Marketplace Performance Report",
        "scope": "platform",
        "period_label": period_label,
        "date_range": date_range_str,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "filters": filter_summary,
        "kpis": [
            {"label": "Platform Revenue", "value": f"KES {revenue:,.0f}"},
            {"label": "Total Orders", "value": f"{total_orders:,}"},
            {"label": "Average Order", "value": f"KES {avg_order_value:,.0f}"},
            {"label": "Active Bakeries", "value": f"{approved_bakeries:,} / {total_bakeries:,}"},
            {"label": "Cakes Catalog", "value": f"{total_cakes:,}"},
            {"label": "Cities Covered", "value": f"{cities_covered:,}"},
        ],
        "sheets": [
            {
                "name": "Summary",
                "columns": ["Metric", "Value"],
                "rows": [
                    ["Reporting Period", period_label],
                    ["Date Range", date_range_str],
                    ["Total Platform Revenue", f"KES {revenue:,.0f}"],
                    ["Total Platform Orders", total_orders],
                    ["Average Order Value", f"KES {avg_order_value:,.0f}"],
                    ["Order Completion Rate", f"{completion_rate}%"],
                    ["Total Bakeries", total_bakeries],
                    ["Approved Bakeries", approved_bakeries],
                    ["Awaiting Approval", pending_bakeries],
                    ["Suspended Bakeries", suspended_bakeries],
                    ["Total Cakes Listed", total_cakes],
                    ["Average Cake Price", f"KES {avg_cake_price:,.0f}"],
                    ["Cities Covered", cities_covered],
                    ["Customer Reviews", total_reviews],
                    ["Average Rating", f"{avg_rating or 'No reviews'} / 5"],
                ],
            },
            {
                "name": "Revenue Trend",
                "columns": ["Date", "Orders", "Revenue (KES)"],
                "money_cols": [2],
                "rows": trend_rows,
            },
            {
                "name": "Order Workflow",
                "columns": ["Stage", "Orders Count", "Share of Total"],
                "rows": [
                    [
                        "Pending",
                        status_counts["PENDING"],
                        f"{(status_counts['PENDING'] / total_orders * 100):.1f}%" if total_orders else "0.0%",
                    ],
                    [
                        "Contacted",
                        status_counts["CONTACTED"],
                        f"{(status_counts['CONTACTED'] / total_orders * 100):.1f}%" if total_orders else "0.0%",
                    ],
                    [
                        "Confirmed",
                        status_counts["CONFIRMED"],
                        f"{(status_counts['CONFIRMED'] / total_orders * 100):.1f}%" if total_orders else "0.0%",
                    ],
                    [
                        "Completed",
                        status_counts["COMPLETED"],
                        f"{(status_counts['COMPLETED'] / total_orders * 100):.1f}%" if total_orders else "0.0%",
                    ],
                    [
                        "Cancelled",
                        status_counts["CANCELLED"],
                        f"{(status_counts['CANCELLED'] / total_orders * 100):.1f}%" if total_orders else "0.0%",
                    ],
                ],
            },
            {
                "name": "Channels",
                "columns": ["Channel", "Orders", "Revenue (KES)"],
                "money_cols": [2],
                "rows": [
                    ["WhatsApp", len(wa_orders), wa_rev],
                    ["M-Pesa", len(mp_orders), mp_rev],
                ],
            },
            {
                "name": "Bakeries Leaderboard",
                "columns": ["Bakery Name", "City", "Orders", "Revenue (KES)"],
                "money_cols": [3],
                "rows": leaderboard_rows,
            },
            {
                "name": "Cities",
                "columns": ["City", "Bakeries Count", "Approved", "Cakes Listed"],
                "rows": cities_rows,
            },
            {
                "name": "Top Cakes",
                "columns": ["Cake Name", "Bakery", "Units Sold", "Revenue (KES)"],
                "money_cols": [3],
                "rows": top_cakes_rows,
            },
            {
                "name": "Recent Orders",
                "columns": ["Date", "Bakery", "Customer", "Phone", "Channel", "Status", "Total (KES)"],
                "money_cols": [6],
                "rows": recent_orders_rows,
            },
            {
                "name": "Customer Ratings",
                "columns": ["Star Rating", "Reviews Count"],
                "rows": ratings_rows,
            },
        ],
    }

    # Generate output
    fmt = format.lower().strip()
    from_stamp = from_dt.strftime("%Y-%m-%d") if from_dt else "all"
    to_stamp = to_dt.strftime("%Y-%m-%d")
    filename = f"crumbly-platform-analytics-{from_stamp}_{to_stamp}"

    if fmt in ("xlsx", "excel"):
        io_data = build_analytics_workbook(report_data)
    elif fmt == "pdf":
        io_data = build_analytics_pdf(report_data)
    elif fmt == "csv":
        io_data = build_analytics_csv(report_data)
    else:
        raise HTTPException(status_code=400, detail="Unsupported format. Use xlsx, pdf, or csv.")

    return get_response(io_data, filename, fmt)


# ──────────────────────────────────────────────── Basic / Legacy Exporters


@router.get("/exports/orders")
async def export_orders(
    format: ExportFormat = Query(..., description="Format to export (csv, excel, pdf)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Order).options(selectinload(Order.bakery)).order_by(Order.createdAt.desc())
    if current_user.role == Role.BAKER.value:
        if not current_user.bakery:
            raise HTTPException(status_code=400, detail="User has no bakery")
        query = query.where(Order.bakeryId == current_user.bakery.id)

    result = await db.execute(query)
    orders = result.scalars().all()

    headers = ["ID", "Customer Name", "Customer Phone", "Status", "Total Amount", "Channel", "Created At"]
    data = []
    for o in orders:
        data.append(
            {
                "ID": o.id,
                "Customer Name": o.customerName,
                "Customer Phone": o.customerPhone,
                "Status": o.status,
                "Total Amount": o.totalAmount,
                "Channel": o.channel,
                "Created At": o.createdAt.strftime("%Y-%m-%d %H:%M") if o.createdAt else "",
            }
        )

    if format == "csv":
        io_data = export_to_csv(headers, data)
    elif format in ("excel", "xlsx"):
        io_data = export_to_excel(headers, data)
    else:
        io_data = export_to_pdf("Orders Export", headers, data)

    return get_response(io_data, "orders_export", format)


@router.get("/exports/products")
async def export_products(
    format: ExportFormat = Query(..., description="Format to export (csv, excel, pdf)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Cake).options(selectinload(Cake.category)).order_by(Cake.createdAt.desc())
    if current_user.role == Role.BAKER.value:
        if not current_user.bakery:
            raise HTTPException(status_code=400, detail="User has no bakery")
        query = query.where(Cake.bakeryId == current_user.bakery.id)

    result = await db.execute(query)
    products = result.scalars().all()

    headers = ["ID", "Name", "Category", "Price", "Discount Price", "Available", "Featured"]
    data = []
    for p in products:
        data.append(
            {
                "ID": p.id,
                "Name": p.name,
                "Category": p.category.name if p.category else "",
                "Price": p.price,
                "Discount Price": p.discountPrice or "",
                "Available": "Yes" if p.isAvailable else "No",
                "Featured": "Yes" if p.isFeatured else "No",
            }
        )

    if format == "csv":
        io_data = export_to_csv(headers, data)
    elif format in ("excel", "xlsx"):
        io_data = export_to_excel(headers, data)
    else:
        io_data = export_to_pdf("Products Export", headers, data)

    return get_response(io_data, "products_export", format)


@router.get("/exports/insights")
async def export_insights(
    format: ExportFormat = Query(..., description="Format to export (csv, excel, pdf)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    headers = ["Metric", "Value"]

    if current_user.role == Role.BAKER.value:
        if not current_user.bakery:
            raise HTTPException(status_code=400, detail="User has no bakery")

        bakery_id = current_user.bakery.id
        orders_result = await db.execute(select(func.count(Order.id)).where(Order.bakeryId == bakery_id))
        total_orders = orders_result.scalar() or 0

        revenue_result = await db.execute(
            select(func.sum(Order.totalAmount)).where(
                Order.bakeryId == bakery_id, Order.status == OrderStatus.COMPLETED.value
            )
        )
        total_revenue = revenue_result.scalar() or 0

        products_result = await db.execute(select(func.count(Cake.id)).where(Cake.bakeryId == bakery_id))
        total_products = products_result.scalar() or 0

        data = [
            {"Metric": "Total Orders", "Value": total_orders},
            {"Metric": "Total Revenue (Completed)", "Value": total_revenue},
            {"Metric": "Total Products", "Value": total_products},
        ]
    else:
        bakeries_result = await db.execute(select(func.count(Bakery.id)))
        total_bakeries = bakeries_result.scalar() or 0

        users_result = await db.execute(select(func.count(User.id)))
        total_users = users_result.scalar() or 0

        orders_result = await db.execute(select(func.count(Order.id)))
        total_orders = orders_result.scalar() or 0

        data = [
            {"Metric": "Total Bakeries", "Value": total_bakeries},
            {"Metric": "Total Users", "Value": total_users},
            {"Metric": "Total Platform Orders", "Value": total_orders},
        ]

    if format == "csv":
        io_data = export_to_csv(headers, data)
    elif format in ("excel", "xlsx"):
        io_data = export_to_excel(headers, data)
    else:
        io_data = export_to_pdf("Insights Export", headers, data)

    return get_response(io_data, "insights_export", format)
