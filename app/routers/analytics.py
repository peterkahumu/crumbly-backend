from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import require_admin, require_baker
from app.database import get_db
from app.models import Bakery, Cake, Category, Order, OrderStatus, PortfolioItem, Review, Role, User

router = APIRouter(prefix="/analytics", tags=["analytics"])


def parse_dates(range_val: str | None = "30d", from_val: str | None = None, to_val: str | None = None):
    now = datetime.now(timezone.utc)
    today = datetime(now.year, now.month, now.day, 23, 59, 59, 999999, tzinfo=timezone.utc)
    days_map = {"7d": 7, "30d": 30, "90d": 90, "6m": 182, "12m": 365}

    if range_val == "all":
        return None, today, "All time"
    if range_val == "custom" and from_val:
        try:
            f_dt = datetime.strptime(from_val[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            t_dt = datetime.strptime(to_val[:10], "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc) if to_val else today
            if f_dt > t_dt:
                f_dt, t_dt = t_dt, f_dt
            return f_dt, t_dt, f"{f_dt.strftime('%b %d, %Y')} – {t_dt.strftime('%b %d, %Y')}"
        except Exception:
            pass

    days = days_map.get(range_val, 30)
    f_dt = today - timedelta(days=days - 1)
    f_dt = datetime(f_dt.year, f_dt.month, f_dt.day, 0, 0, 0, tzinfo=timezone.utc)
    return f_dt, today, f"Last {days} days"


def build_calendar_heatmap(from_dt, to_dt, day_counts):
    start = from_dt if from_dt else (to_dt - timedelta(days=29))
    # Align to previous Sunday (0=Mon...6=Sun in Python, so Sunday is weekday() == 6)
    days_since_sunday = (start.weekday() + 1) % 7
    curr = datetime(start.year, start.month, start.day, tzinfo=timezone.utc) - timedelta(days=days_since_sunday)
    end = datetime(to_dt.year, to_dt.month, to_dt.day, tzinfo=timezone.utc)
    days_to_sat = (5 - end.weekday()) % 7
    end_sat = end + timedelta(days=days_to_sat)

    weeks = []
    current_week = []

    while curr <= end_sat:
        day_str = curr.strftime("%Y-%m-%d")
        d_stat = day_counts.get(day_str, {"orders": 0, "revenue": 0})
        current_week.append({
            "key": day_str,
            "label": curr.strftime("%b %d, %Y"),
            "value": d_stat["orders"],
            "revenue": d_stat["revenue"],
        })
        if len(current_week) == 7:
            first_day = next((d for d in current_week if d is not None), None)
            weeks.append({
                "label": first_day["label"].split(",")[0] if first_day else "",
                "days": current_week,
            })
            current_week = []
        curr += timedelta(days=1)

    if current_week:
        first_day = next((d for d in current_week if d is not None), None)
        while len(current_week) < 7:
            current_week.append(None)
        weeks.append({
            "label": first_day["label"].split(",")[0] if first_day else "",
            "days": current_week,
        })

    return weeks


def build_trend_points(from_dt, to_dt, day_counts):
    start = from_dt if from_dt else (to_dt - timedelta(days=29))
    curr = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end = datetime(to_dt.year, to_dt.month, to_dt.day, tzinfo=timezone.utc)

    raw_points = []
    while curr <= end:
        day_str = curr.strftime("%Y-%m-%d")
        d = day_counts.get(day_str, {"orders": 0, "revenue": 0})
        raw_points.append({
            "day": day_str,
            "label": curr.strftime("%b %d"),
            "orders": d["orders"],
            "revenue": d["revenue"],
        })
        curr += timedelta(days=1)

    # 7-point moving average
    points = []
    for idx, p in enumerate(raw_points):
        window = raw_points[max(0, idx - 6):idx + 1]
        rev_avg = round(sum(w["revenue"] for w in window) / len(window)) if window else p["revenue"]
        ord_avg = round(sum(w["orders"] for w in window) / len(window), 1) if window else p["orders"]
        points.append({
            **p,
            "revenueAvg": rev_avg,
            "ordersAvg": ord_avg,
            "maRevenue": rev_avg,
            "maOrders": ord_avg,
        })
    return points


@router.get("/baker")
async def get_baker_analytics(
    range_val: str | None = Query("30d", alias="range"),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    current_user: User = Depends(require_baker),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.bakery:
        return {"error": "Bakery not found"}

    bakery_id = current_user.bakery.id
    from_dt, to_dt, period_label = parse_dates(range_val, from_date, to_date)

    # Orders query
    order_stmt = select(Order).where(Order.bakeryId == bakery_id)
    if from_dt:
        order_stmt = order_stmt.where(Order.createdAt >= from_dt)
    if to_dt:
        order_stmt = order_stmt.where(Order.createdAt <= to_dt)
    order_stmt = order_stmt.order_by(Order.createdAt.desc())

    orders = (await db.execute(order_stmt)).scalars().all()

    # Cakes query
    cakes = (await db.execute(
        select(Cake).options(selectinload(Cake.category)).where(Cake.bakeryId == bakery_id)
    )).scalars().all()

    # Portfolio query
    portfolio_items = (await db.execute(
        select(PortfolioItem).where(PortfolioItem.bakeryId == bakery_id)
    )).scalars().all()

    # Reviews query
    review_stmt = select(Review).where(Review.bakeryId == bakery_id)
    if from_dt:
        review_stmt = review_stmt.where(Review.createdAt >= from_dt)
    if to_dt:
        review_stmt = review_stmt.where(Review.createdAt <= to_dt)
    reviews = (await db.execute(review_stmt)).scalars().all()

    # Aggregations
    orders_count = len(orders)
    revenue = sum(o.totalAmount for o in orders if o.status != OrderStatus.CANCELLED.value)
    avg_order_value = round(revenue / orders_count) if orders_count else 0

    status_counts = {s.value: 0 for s in OrderStatus}
    channel_counts = {}
    day_counts = {}

    for o in orders:
        status_counts[o.status] = status_counts.get(o.status, 0) + 1
        ch = o.channel or "WHATSAPP"
        if ch not in channel_counts:
            channel_counts[ch] = {"orders": 0, "revenue": 0}
        channel_counts[ch]["orders"] += 1
        if o.status != OrderStatus.CANCELLED.value:
            channel_counts[ch]["revenue"] += o.totalAmount

        day_str = o.createdAt.strftime("%Y-%m-%d") if o.createdAt else "Unknown"
        if day_str not in day_counts:
            day_counts[day_str] = {"orders": 0, "revenue": 0}
        day_counts[day_str]["orders"] += 1
        if o.status != OrderStatus.CANCELLED.value:
            day_counts[day_str]["revenue"] += o.totalAmount

    pending_count = status_counts.get("PENDING", 0)
    completed_count = status_counts.get("COMPLETED", 0)
    cancelled_count = status_counts.get("CANCELLED", 0)
    completion_rate = round((completed_count / orders_count) * 100) if orders_count else 0

    # Heatmap and Trend
    heatmap = build_calendar_heatmap(from_dt, to_dt, day_counts)
    trend_points = build_trend_points(from_dt, to_dt, day_counts)

    # Channels
    channels = []
    for ch, d in channel_counts.items():
        channels.append({
            "channel": ch,
            "label": "WhatsApp" if ch == "WHATSAPP" else "M-Pesa",
            "count": d["orders"],
            "orders": d["orders"],
            "revenue": d["revenue"],
            "pct": round((d["orders"] / orders_count) * 100) if orders_count else 0,
        })

    # Top cakes from items
    cake_demand = {}
    for o in orders:
        if o.status == OrderStatus.CANCELLED.value:
            continue
        for item in (o.items or []):
            cid = item.get("cakeId") or item.get("name") or "other"
            name = item.get("name") or "Unknown cake"
            qty = int(item.get("qty") or 1)
            pr = int(item.get("price") or 0)
            if cid not in cake_demand:
                cake_demand[cid] = {"name": name, "qty": 0, "revenue": 0, "category": "Cakes"}
            cake_demand[cid]["qty"] += qty
            cake_demand[cid]["revenue"] += qty * pr

    top_cakes = sorted(
        [{"id": cid, **vals} for cid, vals in cake_demand.items()],
        key=lambda x: x["revenue"],
        reverse=True,
    )[:10]

    # Category demand and supply
    cat_supply_counts = {}
    for c in cakes:
        cat_name = c.category.name if c.category else "Other"
        cat_supply_counts[cat_name] = cat_supply_counts.get(cat_name, 0) + 1

    category_supply = [{"label": k, "value": v} for k, v in cat_supply_counts.items()]

    # Portfolio mix
    event_counts = {}
    for p in portfolio_items:
        et = p.eventType or "Other"
        event_counts[et] = event_counts.get(et, 0) + 1
    portfolio_mix = [{"label": k, "value": v} for k, v in event_counts.items()]

    # Ratings
    ratings_total = len(reviews)
    ratings_avg = round(sum(r.rating for r in reviews) / ratings_total, 1) if ratings_total else None
    breakdown = []
    for stars in [5, 4, 3, 2, 1]:
        count = sum(1 for r in reviews if r.rating == stars)
        breakdown.append({"rating": stars, "label": f"{stars} star{'s' if stars > 1 else ''}", "value": count})

    # Funnel
    funnel = [
        {"stage": "Placed", "label": "Placed", "count": orders_count, "pct": 100},
        {"stage": "Contacted", "label": "Contacted", "count": status_counts.get("CONTACTED", 0) + status_counts.get("CONFIRMED", 0) + completed_count, "pct": round(((status_counts.get("CONTACTED", 0) + status_counts.get("CONFIRMED", 0) + completed_count) / orders_count) * 100) if orders_count else 0},
        {"stage": "Confirmed", "label": "Confirmed", "count": status_counts.get("CONFIRMED", 0) + completed_count, "pct": round(((status_counts.get("CONFIRMED", 0) + completed_count) / orders_count) * 100) if orders_count else 0},
        {"stage": "Completed", "label": "Completed", "count": completed_count, "pct": completion_rate},
    ]

    return {
        "totals": {
            "orders": orders_count,
            "revenue": revenue,
            "avgOrderValue": avg_order_value,
            "pending": pending_count,
            "completionRate": completion_rate,
            "cakes": len(cakes),
            "available": sum(1 for c in cakes if c.isAvailable),
            "discounted": sum(1 for c in cakes if c.discountPrice is not None),
            "portfolio": len(portfolio_items),
        },
        "statusCounts": status_counts,
        "cancelled": cancelled_count,
        "window": {"label": period_label},
        "comparison": {"revenueDelta": 0, "ordersDelta": 0},
        "trend": {"size": "day", "averageWindow": 7, "points": trend_points},
        "heatmap": heatmap,
        "funnel": funnel,
        "channels": channels,
        "topCakes": top_cakes,
        "categoryDemand": [],
        "categorySupply": category_supply,
        "priceBins": [],
        "priceStats": None,
        "portfolioMix": portfolio_mix,
        "ratings": {"total": ratings_total, "average": ratings_avg, "breakdown": breakdown},
    }


@router.get("/platform")
async def get_platform_analytics(
    range_val: str | None = Query("30d", alias="range"),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    city: str | None = Query(None),
    bakery_id: str | None = Query(None, alias="bakery"),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    from_dt, to_dt, period_label = parse_dates(range_val, from_date, to_date)

    # 1. Orders
    order_stmt = select(Order).options(selectinload(Order.bakery))
    if from_dt:
        order_stmt = order_stmt.where(Order.createdAt >= from_dt)
    if to_dt:
        order_stmt = order_stmt.where(Order.createdAt <= to_dt)
    if city:
        order_stmt = order_stmt.join(Bakery, Order.bakeryId == Bakery.id).where(Bakery.city == city)
    if bakery_id:
        order_stmt = order_stmt.where(Order.bakeryId == bakery_id)
    order_stmt = order_stmt.order_by(Order.createdAt.desc())

    orders = (await db.execute(order_stmt)).scalars().all()

    # 2. Bakeries
    bakeries = (await db.execute(select(Bakery).order_by(Bakery.createdAt.desc()))).scalars().all()

    # 3. Cakes
    cakes = (await db.execute(select(Cake).options(selectinload(Cake.category), selectinload(Cake.bakery)))).scalars().all()

    # 4. Reviews
    reviews = (await db.execute(select(Review))).scalars().all()

    # Platform Totals
    orders_count = len(orders)
    revenue = sum(o.totalAmount for o in orders if o.status != OrderStatus.CANCELLED.value)
    avg_order_value = round(revenue / orders_count) if orders_count else 0

    bakery_statuses = {}
    city_bakeries = {}
    city_cakes = {}

    for b in bakeries:
        bakery_statuses[b.status] = bakery_statuses.get(b.status, 0) + 1
        c_name = b.city or "Nairobi"
        if c_name not in city_bakeries:
            city_bakeries[c_name] = {"total": 0, "approved": 0}
        city_bakeries[c_name]["total"] += 1
        if b.status == "APPROVED":
            city_bakeries[c_name]["approved"] += 1

    for c in cakes:
        if c.bakery and c.bakery.city:
            c_name = c.bakery.city
            city_cakes[c_name] = city_cakes.get(c_name, 0) + 1

    status_counts = {s.value: 0 for s in OrderStatus}
    channel_counts = {}
    day_counts = {}
    bakery_revenue = {}

    for o in orders:
        status_counts[o.status] = status_counts.get(o.status, 0) + 1
        ch = o.channel or "WHATSAPP"
        if ch not in channel_counts:
            channel_counts[ch] = {"orders": 0, "revenue": 0}
        channel_counts[ch]["orders"] += 1

        b_name = o.bakery.name if o.bakery else "Unknown"
        if b_name not in bakery_revenue:
            bakery_revenue[b_name] = {"orders": 0, "revenue": 0}
        bakery_revenue[b_name]["orders"] += 1

        if o.status != OrderStatus.CANCELLED.value:
            channel_counts[ch]["revenue"] += o.totalAmount
            bakery_revenue[b_name]["revenue"] += o.totalAmount

        day_str = o.createdAt.strftime("%Y-%m-%d") if o.createdAt else "Unknown"
        if day_str not in day_counts:
            day_counts[day_str] = {"orders": 0, "revenue": 0}
        day_counts[day_str]["orders"] += 1
        if o.status != OrderStatus.CANCELLED.value:
            day_counts[day_str]["revenue"] += o.totalAmount

    # Leaderboard
    leaderboard = sorted(
        [{"label": name, "bakery": name, "value": vals["revenue"], "orders": vals["orders"]} for name, vals in bakery_revenue.items()],
        key=lambda x: x["value"],
        reverse=True,
    )[:10]

    # Heatmap and Trend
    heatmap = build_calendar_heatmap(from_dt, to_dt, day_counts)
    trend_points = build_trend_points(from_dt, to_dt, day_counts)

    # Recent orders
    recent_orders = []
    for o in orders[:15]:
        recent_orders.append({
            "id": o.id,
            "bakery": o.bakery.name if o.bakery else "Unknown",
            "customerName": o.customerName,
            "channel": o.channel,
            "totalAmount": o.totalAmount,
            "status": o.status,
            "createdAt": o.createdAt.isoformat() if o.createdAt else None,
        })

    # Pending bakers
    pending_bakers = []
    for b in [x for x in bakeries if x.status == "PENDING"][:10]:
        pending_bakers.append({
            "id": b.id,
            "name": b.name,
            "city": b.city,
            "whatsappNumber": b.whatsappNumber,
            "createdAt": b.createdAt.isoformat() if b.createdAt else None,
        })

    # Channels
    channels = []
    for ch, d in channel_counts.items():
        channels.append({
            "channel": ch,
            "label": "WhatsApp" if ch == "WHATSAPP" else "M-Pesa",
            "count": d["orders"],
            "orders": d["orders"],
            "revenue": d["revenue"],
            "pct": round((d["orders"] / orders_count) * 100) if orders_count else 0,
        })

    # Cities list
    cities_list = []
    for c_name, b_info in city_bakeries.items():
        cities_list.append({
            "label": c_name,
            "value": b_info["total"],
            "approved": b_info["approved"],
            "cakes": city_cakes.get(c_name, 0),
        })

    # Status mix
    status_mix = [{"status": k, "label": k.capitalize(), "value": v} for k, v in bakery_statuses.items()]

    # Ratings
    ratings_total = len(reviews)
    ratings_avg = round(sum(r.rating for r in reviews) / ratings_total, 1) if ratings_total else None
    breakdown = []
    for stars in [5, 4, 3, 2, 1]:
        count = sum(1 for r in reviews if r.rating == stars)
        breakdown.append({"rating": stars, "label": f"{stars} star{'s' if stars > 1 else ''}", "value": count})

    # Funnel
    completed_count = status_counts.get("COMPLETED", 0)
    completion_rate = round((completed_count / orders_count) * 100) if orders_count else 0
    funnel = [
        {"stage": "Placed", "label": "Placed", "count": orders_count, "pct": 100},
        {"stage": "Contacted", "label": "Contacted", "count": status_counts.get("CONTACTED", 0) + status_counts.get("CONFIRMED", 0) + completed_count, "pct": round(((status_counts.get("CONTACTED", 0) + status_counts.get("CONFIRMED", 0) + completed_count) / orders_count) * 100) if orders_count else 0},
        {"stage": "Confirmed", "label": "Confirmed", "count": status_counts.get("CONFIRMED", 0) + completed_count, "pct": round(((status_counts.get("CONFIRMED", 0) + completed_count) / orders_count) * 100) if orders_count else 0},
        {"stage": "Completed", "label": "Completed", "count": completed_count, "pct": completion_rate},
    ]

    return {
        "totals": {
            "orders": orders_count,
            "revenue": revenue,
            "avgOrderValue": avg_order_value,
            "bakeries": len(bakeries),
            "cakes": len(cakes),
            "cities": len(city_bakeries),
            "approved": bakery_statuses.get("APPROVED", 0),
            "pending": bakery_statuses.get("PENDING", 0),
            "suspended": bakery_statuses.get("SUSPENDED", 0),
        },
        "window": {"label": period_label},
        "comparison": {"revenueDelta": 0, "ordersDelta": 0},
        "trend": {"size": "day", "averageWindow": 7, "points": trend_points},
        "heatmap": heatmap,
        "funnel": funnel,
        "cancelled": status_counts.get("CANCELLED", 0),
        "statusCounts": status_counts,
        "channels": channels,
        "cities": cities_list,
        "statusMix": status_mix,
        "leaderboard": leaderboard,
        "categoryBalance": [],
        "topCakes": [],
        "priceBins": [],
        "priceStats": None,
        "ratings": {"total": ratings_total, "average": ratings_avg, "breakdown": breakdown},
        "recentOrders": recent_orders,
        "pendingBakers": pending_bakers,
        "options": {
            "cities": list(city_bakeries.keys()),
            "bakeries": [{"id": b.id, "name": b.name} for b in bakeries],
        },
        "appliedFilters": {
            "city": city,
            "bakeryId": bakery_id,
        },
    }
