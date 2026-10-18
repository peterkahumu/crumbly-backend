"""
Seed script for the Crumbly FastAPI backend.

Creates categories, a super-admin user, multiple baker users with bakeries,
cakes, portfolio items, orders (with realistic time-series data), reviews,
conversations, and messages.

Designed to be idempotent: every insert is guarded by an existence check so
re-running this script never duplicates data or crashes.

Usage:
    cd backend
    source venv/bin/activate
    python -m app.seed
"""

import asyncio
import random
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.config import get_settings
from app.database import async_session, engine
from app.models import (
    Bakery,
    BakeryStatus,
    Cake,
    Category,
    Conversation,
    Base,
    Message,
    Notification,
    Order,
    OrderChannel,
    OrderStatus,
    PasswordResetToken,
    PortfolioItem,
    Review,
    Role,
    User,
)
from app.utils.email import send_admin_invitation_email


import os
import logging

SUPER_ADMIN_EMAIL = os.getenv("SUPER_ADMIN_EMAIL")
SUPER_ADMIN_NAME = os.getenv("SUPER_ADMIN_NAME") or "Platform Administrator"

BAKER_PASSWORD = os.getenv("BAKER_PASSWORD")

if not SUPER_ADMIN_EMAIL or not BAKER_PASSWORD:
    logging.warning("SUPER_ADMIN_EMAIL or BAKER_PASSWORD not found. Skipping seed.")
    exit(1)

CATEGORIES = [
    {"name": "Birthday Cakes", "slug": "birthday-cakes", "icon": "cake"},
    {"name": "Wedding Cakes", "slug": "wedding-cakes", "icon": "heart"},
    {"name": "Cupcakes", "slug": "cupcakes", "icon": "cookie"},
    {"name": "Pastries", "slug": "pastries", "icon": "croissant"},
    {"name": "Custom Cakes", "slug": "custom-cakes", "icon": "palette"},
    {"name": "Bread & Rolls", "slug": "bread-rolls", "icon": "wheat"},
    {"name": "Cookies", "slug": "cookies", "icon": "cookie"},
    {"name": "Desserts", "slug": "desserts", "icon": "ice-cream"},
]

BAKERIES = [
    {
        "owner": {"name": "Jane Wanjiku", "email": "jane@sweetcrumbs.co.ke", "phone": "+254783925820"},
        "bakery": {
            "name": "Sweet Crumbs Bakery",
            "slug": "sweet-crumbs-bakery",
            "description": "Artisan cakes baked with love in Nairobi. We specialise in celebration cakes, cupcakes, and pastries made from locally sourced ingredients.",
            "whatsappNumber": "+254783925820",
            "mpesaTillNumber": "123456",
            "city": "Nairobi",
            "address": "Westlands, Nairobi",
            "status": BakeryStatus.APPROVED.value,
        },
    },
    {
        "owner": {"name": "Peter Odhiambo", "email": "peter@frostedoven.co.ke", "phone": "+254783925820"},
        "bakery": {
            "name": "The Frosted Oven",
            "slug": "the-frosted-oven",
            "description": "Premium baked goods from our family-run kitchen. Wedding cakes, birthday cakes, and everything in between.",
            "whatsappNumber": "+254783925820",
            "mpesaTillNumber": "234567",
            "city": "Nairobi",
            "address": "Kilimani, Nairobi",
            "status": BakeryStatus.APPROVED.value,
        },
    },
    {
        "owner": {"name": "Amina Hassan", "email": "amina@sugarspice.co.ke", "phone": "+254783925820"},
        "bakery": {
            "name": "Sugar & Spice Patisserie",
            "slug": "sugar-spice-patisserie",
            "description": "French-inspired patisserie in Mombasa. We bring continental flavours to the Kenyan coast.",
            "whatsappNumber": "+254783925820",
            "mpesaTillNumber": "345678",
            "city": "Mombasa",
            "address": "Nyali, Mombasa",
            "status": BakeryStatus.APPROVED.value,
        },
    },
    {
        "owner": {"name": "David Kimani", "email": "david@goldenwhisk.co.ke", "phone": "+254783925820"},
        "bakery": {
            "name": "Golden Whisk Bakehouse",
            "slug": "golden-whisk-bakehouse",
            "description": "A warm bakehouse in Kisumu known for rich chocolate cakes and freshly baked bread.",
            "whatsappNumber": "+254783925820",
            "city": "Kisumu",
            "address": "Milimani, Kisumu",
            "status": BakeryStatus.APPROVED.value,
        },
    },
    {
        "owner": {"name": "Grace Muthoni", "email": "grace@buttercream.co.ke", "phone": "+254783925820"},
        "bakery": {
            "name": "Buttercream Dreams",
            "slug": "buttercream-dreams",
            "description": "Custom celebration cakes and gourmet cupcakes for every occasion. Based in Nairobi.",
            "whatsappNumber": "+254783925820",
            "mpesaTillNumber": "456789",
            "city": "Nairobi",
            "address": "Karen, Nairobi",
            "status": BakeryStatus.APPROVED.value,
        },
    },
    {
        "owner": {"name": "Samuel Njoroge", "email": "samuel@cocoaandcream.co.ke", "phone": "+254783925820"},
        "bakery": {
            "name": "Cocoa & Cream Cakery",
            "slug": "cocoa-and-cream-cakery",
            "description": "Chocolatiers and cake artists. We craft stunning chocolate creations for weddings and corporate events.",
            "whatsappNumber": "+254783925820",
            "mpesaTillNumber": "567890",
            "city": "Nakuru",
            "address": "CBD, Nakuru",
            "status": BakeryStatus.APPROVED.value,
        },
    },
    {
        "owner": {"name": "Faith Atieno", "email": "faith@velvetslice.co.ke", "phone": "+254783925820"},
        "bakery": {
            "name": "The Velvet Slice",
            "slug": "the-velvet-slice",
            "description": "Elegant, minimalist cake designs. We believe less is more — simple beauty, extraordinary taste.",
            "whatsappNumber": "+254783925820",
            "city": "Nairobi",
            "address": "Lavington, Nairobi",
            "status": BakeryStatus.APPROVED.value,
        },
    },
    {
        "owner": {"name": "Brian Kiprotich", "email": "brian@honeycomb.co.ke", "phone": "+254783925820"},
        "bakery": {
            "name": "Honeycomb Bakes",
            "slug": "honeycomb-bakes",
            "description": "Honey-infused bakes and rustic breads from Eldoret. Farm-to-table baking at its finest.",
            "whatsappNumber": "+254783925820",
            "city": "Eldoret",
            "address": "Kapseret, Eldoret",
            "status": BakeryStatus.APPROVED.value,
        },
    },
    {
        "owner": {"name": "Lucy Wambui", "email": "lucy@petalicing.co.ke", "phone": "+254783925820"},
        "bakery": {
            "name": "Petal & Icing Cakes",
            "slug": "petal-and-icing-cakes",
            "description": "Floral cake art and sugar flowers. We create edible masterpieces for weddings and high-end events.",
            "whatsappNumber": "+254783925820",
            "city": "Nairobi",
            "address": "Runda, Nairobi",
            "status": BakeryStatus.PENDING.value,
        },
    },
    {
        "owner": {"name": "Kevin Otieno", "email": "kevin@riseshine.co.ke", "phone": "+254783925820"},
        "bakery": {
            "name": "Rise & Shine Bakery",
            "slug": "rise-and-shine-bakery",
            "description": "Early-morning fresh pastries and artisan bread delivered to your door in Thika.",
            "whatsappNumber": "+254783925820",
            "city": "Thika",
            "address": "Makongeni, Thika",
            "status": BakeryStatus.SUSPENDED.value,
        },
    },
]

CAKE_TEMPLATES = [
    {"name": "Classic Vanilla Cake", "price": 2500, "category_slug": "birthday-cakes", "featured": True},
    {"name": "Rich Chocolate Layer Cake", "price": 3000, "category_slug": "birthday-cakes", "featured": True},
    {"name": "Red Velvet Cake", "price": 3200, "category_slug": "birthday-cakes", "featured": False},
    {"name": "Carrot Cake with Cream Cheese", "price": 2800, "category_slug": "birthday-cakes", "featured": False},
    {"name": "Lemon Drizzle Cake", "price": 2200, "category_slug": "birthday-cakes", "featured": False},
    {"name": "Elegant White Wedding Cake", "price": 15000, "category_slug": "wedding-cakes", "featured": True},
    {"name": "Tiered Fondant Wedding Cake", "price": 25000, "category_slug": "wedding-cakes", "featured": True},
    {"name": "Rustic Naked Wedding Cake", "price": 12000, "category_slug": "wedding-cakes", "featured": False},
    {"name": "Assorted Cupcake Box (12)", "price": 1800, "category_slug": "cupcakes", "featured": True},
    {"name": "Red Velvet Cupcakes (6)", "price": 1200, "category_slug": "cupcakes", "featured": False},
    {"name": "Vanilla Bean Cupcakes (6)", "price": 1000, "category_slug": "cupcakes", "featured": False},
    {"name": "Butter Croissant", "price": 250, "category_slug": "pastries", "featured": False},
    {"name": "Danish Pastry", "price": 300, "category_slug": "pastries", "featured": False},
    {"name": "Cinnamon Rolls (4)", "price": 600, "category_slug": "pastries", "featured": True},
    {"name": "Custom Photo Cake", "price": 4500, "category_slug": "custom-cakes", "featured": True},
    {"name": "3D Sculpted Character Cake", "price": 8000, "category_slug": "custom-cakes", "featured": False},
    {"name": "Sourdough Loaf", "price": 450, "category_slug": "bread-rolls", "featured": False},
    {"name": "Dinner Rolls (8)", "price": 350, "category_slug": "bread-rolls", "featured": False},
    {"name": "Chocolate Chip Cookies (12)", "price": 800, "category_slug": "cookies", "featured": True},
    {"name": "Macaron Assortment (12)", "price": 1500, "category_slug": "cookies", "featured": False},
    {"name": "Tiramisu", "price": 1800, "category_slug": "desserts", "featured": True},
    {"name": "Crème Brûlée (2)", "price": 1200, "category_slug": "desserts", "featured": False},
]

EVENT_TYPES = ["Wedding", "Birthday", "Corporate", "Baby Shower", "Anniversary", "Graduation"]
CUSTOMER_NAMES = [
    "Alice Mwangi", "Bob Kamau", "Catherine Nyambura", "Dennis Ochieng",
    "Elizabeth Akinyi", "Frank Mutua", "Hannah Njeri", "Isaac Wafula",
    "Josephine Chebet", "Kennedy Maina", "Lilian Wanjiku", "Michael Ouma",
    "Nancy Adhiambo", "Oscar Kipkoech", "Patricia Wangari", "Robert Mulwa",
]
CUSTOMER_PHONES = ["+254783925820"] * len(CUSTOMER_NAMES)

REVIEW_COMMENTS = [
    "Absolutely amazing cake! The fondant was perfect.",
    "Best cupcakes in town. Will order again!",
    "The wedding cake exceeded our expectations. Thank you!",
    "Good quality, but delivery was a bit late.",
    "Great taste but the decoration could be better.",
    "Five stars! Everything was perfect from ordering to delivery.",
    "Our guests couldn't stop talking about the cake. Superb!",
    "Decent cake for the price. Would recommend.",
    "The chocolate cake was incredibly rich and delicious.",
    "Beautiful cake design and wonderful flavour. Highly recommend!",
    "Very creative custom cake. My kids loved it!",
    "Fresh pastries, would definitely order more.",
]


# ──────────────────────────────── Helpers

async def get_or_create(session: AsyncSession, model, defaults: dict, **lookup):
    """Return (instance, created). Never duplicates."""
    stmt = select(model)
    for k, v in lookup.items():
        stmt = stmt.where(getattr(model, k) == v)
    existing = await session.scalar(stmt)
    if existing:
        return existing, False
    obj = model(**lookup, **defaults)
    session.add(obj)
    await session.flush()
    return obj, True


def random_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    secs = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=secs)


def make_slug(name: str) -> str:
    import re
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


# ──────────────────────────────── Seed functions

async def seed_categories(session: AsyncSession) -> dict[str, Category]:
    print("Seeding categories...")
    cat_map: dict[str, Category] = {}
    for c in CATEGORIES:
        cat, created = await get_or_create(
            session, Category, defaults={"icon": c["icon"]}, name=c["name"], slug=c["slug"]
        )
        cat_map[c["slug"]] = cat
        if created:
            print(f"  ✓ Category: {c['name']}")
        else:
            print(f"  — Category already exists: {c['name']}")
    return cat_map


async def seed_super_admin(session: AsyncSession) -> User:
    print("Seeding super admin...")
    admin, created = await get_or_create(
        session,
        User,
        defaults={
            "name": SUPER_ADMIN_NAME,
            "passwordHash": "!",
            "role": Role.SUPER_ADMIN.value,
        },
        email=SUPER_ADMIN_EMAIL,
    )
    if created or admin.passwordHash == "!":
        token = str(uuid.uuid4())
        expires = datetime.now(timezone.utc) + timedelta(hours=48)

        old_tokens = await session.scalars(
            select(PasswordResetToken).where(PasswordResetToken.email == SUPER_ADMIN_EMAIL)
        )
        for ot in old_tokens:
            await session.delete(ot)

        reset_token = PasswordResetToken(
            email=SUPER_ADMIN_EMAIL,
            token=token,
            expiresAt=expires,
        )
        session.add(reset_token)
        await session.flush()

        settings = get_settings()
        setup_url = f"{settings.frontend_url}/auth/reset-password?token={token}"
        await send_admin_invitation_email(
            to_email=SUPER_ADMIN_EMAIL,
            setup_url=setup_url,
            recipient_name=admin.name,
        )
        print(f"  ✓ Super Admin provisioned: {SUPER_ADMIN_EMAIL} (invitation dispatched with password setup link)")
    else:
        print(f"  — Super Admin already exists: {SUPER_ADMIN_EMAIL} (active)")
    return admin


async def seed_bakeries_and_users(session: AsyncSession) -> list[tuple[User, Bakery]]:
    print("Seeding bakeries and baker users...")
    pairs = []
    for b in BAKERIES:
        user, user_created = await get_or_create(
            session,
            User,
            defaults={
                "name": b["owner"]["name"],
                "passwordHash": hash_password(BAKER_PASSWORD),
                "phone": b["owner"]["phone"],
                "role": Role.BAKER.value,
            },
            email=b["owner"]["email"],
        )

        bakery_data = dict(b["bakery"])
        slug = bakery_data.pop("slug")
        name = bakery_data.pop("name")

        bakery, bakery_created = await get_or_create(
            session,
            Bakery,
            defaults={**bakery_data, "name": name},
            ownerId=user.id,
            slug=slug,
        )

        pairs.append((user, bakery))
        label = "✓" if user_created else "—"
        print(f"  {label} {bakery.name} ({bakery.status}) — owner: {user.email}")

    return pairs


async def seed_cakes(
    session: AsyncSession,
    bakery_pairs: list[tuple[User, Bakery]],
    cat_map: dict[str, Category],
) -> list[Cake]:
    print("Seeding cakes...")
    all_cakes = []
    for user, bakery in bakery_pairs:
        # Each bakery gets a random subset of cake templates
        count = random.randint(8, len(CAKE_TEMPLATES))
        templates = random.sample(CAKE_TEMPLATES, count)
        for tpl in templates:
            category = cat_map.get(tpl["category_slug"])
            if not category:
                continue

            base_slug = make_slug(tpl["name"])
            cake_slug = f"{base_slug}"

            # Check if this cake already exists for this bakery
            existing = await session.scalar(
                select(Cake).where(Cake.bakeryId == bakery.id, Cake.slug == cake_slug)
            )
            if existing:
                all_cakes.append(existing)
                continue

            price = tpl["price"] + random.randint(-200, 500)
            discount = price - random.randint(100, 400) if random.random() < 0.3 else None

            cake = Cake(
                bakeryId=bakery.id,
                categoryId=category.id,
                name=tpl["name"],
                slug=cake_slug,
                description=f"Delicious {tpl['name'].lower()} from {bakery.name}.",
                price=price,
                discountPrice=discount,
                images=[
                    f"https://placehold.co/600x400/EEE/31343C?text={make_slug(tpl['name'])}"
                ],
                isAvailable=True,
                isFeatured=tpl["featured"],
                createdAt=random_date(
                    datetime(2025, 1, 1, tzinfo=timezone.utc),
                    datetime(2026, 6, 1, tzinfo=timezone.utc),
                ),
            )
            session.add(cake)
            all_cakes.append(cake)

    await session.flush()
    cake_counts = {}
    for c in all_cakes:
        cake_counts[c.bakeryId] = cake_counts.get(c.bakeryId, 0) + 1
    for user, bakery in bakery_pairs:
        print(f"  ✓ {bakery.name}: {cake_counts.get(bakery.id, 0)} cakes")
    return all_cakes


async def seed_portfolio(session: AsyncSession, bakery_pairs: list[tuple[User, Bakery]]):
    print("Seeding portfolio items...")
    for user, bakery in bakery_pairs:
        if bakery.status not in (BakeryStatus.APPROVED.value,):
            continue
        existing = await session.scalar(
            select(PortfolioItem).where(PortfolioItem.bakeryId == bakery.id)
        )
        if existing:
            print(f"  — Portfolio items already exist for {bakery.name}")
            continue

        count = random.randint(3, 8)
        for i in range(count):
            event = random.choice(EVENT_TYPES)
            item = PortfolioItem(
                bakeryId=bakery.id,
                imageUrl=f"https://placehold.co/800x600/EEE/31343C?text={event}+{i+1}",
                caption=f"{event} cake for a special client",
                eventType=event,
                createdAt=random_date(
                    datetime(2025, 1, 1, tzinfo=timezone.utc),
                    datetime(2026, 8, 1, tzinfo=timezone.utc),
                ),
            )
            session.add(item)
        print(f"  ✓ {bakery.name}: {count} portfolio items")


async def seed_orders(
    session: AsyncSession,
    bakery_pairs: list[tuple[User, Bakery]],
    all_cakes: list[Cake],
) -> list[Order]:
    print("Seeding orders (time-series data)...")
    all_orders = []
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=365)

    cakes_by_bakery: dict[str, list[Cake]] = {}
    for c in all_cakes:
        cakes_by_bakery.setdefault(c.bakeryId, []).append(c)

    for user, bakery in bakery_pairs:
        # Check if orders already exist
        existing_count_result = await session.scalar(
            select(Order).where(Order.bakeryId == bakery.id)
        )
        if existing_count_result:
            print(f"  — Orders already exist for {bakery.name}")
            continue

        bakery_cakes = cakes_by_bakery.get(bakery.id, [])
        if not bakery_cakes:
            continue

        order_count = random.randint(40, 120)
        statuses = list(OrderStatus)
        channels = list(OrderChannel)

        for _ in range(order_count):
            num_items = random.randint(1, 4)
            selected_cakes = random.choices(bakery_cakes, k=num_items)
            items = []
            total = 0
            for cake in selected_cakes:
                qty = random.randint(1, 3)
                price = cake.discountPrice or cake.price
                items.append({
                    "cakeId": cake.id,
                    "name": cake.name,
                    "qty": qty,
                    "price": price,
                })
                total += qty * price

            order_status = random.choices(
                [s.value for s in statuses],
                weights=[10, 10, 15, 50, 15],
                k=1,
            )[0]
            channel = random.choice([c.value for c in channels])

            order = Order(
                bakeryId=bakery.id,
                customerName=random.choice(CUSTOMER_NAMES),
                customerPhone=random.choice(CUSTOMER_PHONES),
                items=items,
                totalAmount=total,
                status=order_status,
                channel=channel,
                mpesaReceiptNumber=f"QK{random.randint(10000000, 99999999)}" if channel == "MPESA" else None,
                createdAt=random_date(start, now),
            )
            session.add(order)
            all_orders.append(order)

        print(f"  ✓ {bakery.name}: {order_count} orders seeded")

    await session.flush()
    return all_orders


async def seed_reviews(session: AsyncSession, bakery_pairs: list[tuple[User, Bakery]]):
    print("Seeding reviews...")
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=365)

    for user, bakery in bakery_pairs:
        if bakery.status != BakeryStatus.APPROVED.value:
            continue

        existing = await session.scalar(
            select(Review).where(Review.bakeryId == bakery.id)
        )
        if existing:
            print(f"  — Reviews already exist for {bakery.name}")
            continue

        review_count = random.randint(8, 25)
        for _ in range(review_count):
            review = Review(
                bakeryId=bakery.id,
                customerName=random.choice(CUSTOMER_NAMES),
                rating=random.choices([5, 4, 3, 2, 1], weights=[40, 30, 15, 10, 5], k=1)[0],
                comment=random.choice(REVIEW_COMMENTS),
                createdAt=random_date(start, now),
            )
            session.add(review)
        print(f"  ✓ {bakery.name}: {review_count} reviews")


async def seed_conversations_and_messages(
    session: AsyncSession,
    bakery_pairs: list[tuple[User, Bakery]],
):
    print("Seeding sample conversations and messages...")
    now = datetime.now(timezone.utc)

    for user, bakery in bakery_pairs:
        if bakery.status != BakeryStatus.APPROVED.value:
            continue

        existing = await session.scalar(
            select(Conversation).where(Conversation.bakery_id == bakery.id)
        )
        if existing:
            print(f"  — Conversations already exist for {bakery.name}")
            continue

        conv_count = random.randint(2, 5)
        for i in range(conv_count):
            customer_name = random.choice(CUSTOMER_NAMES)
            conv = Conversation(
                bakery_id=bakery.id,
                customer_token=secrets.token_urlsafe(32),
                subject=f"Inquiry from {customer_name}",
                is_closed=random.random() < 0.3,
                created_at=random_date(now - timedelta(days=60), now),
            )
            session.add(conv)
            await session.flush()

            # Add messages to the conversation
            msg_count = random.randint(2, 6)
            msg_time = conv.created_at
            for j in range(msg_count):
                sender_type = "CUSTOMER" if j % 2 == 0 else "BAKER"
                content = (
                    f"Hi, I'd like to inquire about ordering a cake for my event."
                    if j == 0
                    else random.choice([
                        "Thank you for reaching out! What kind of cake are you looking for?",
                        "I'd like a 3-tier wedding cake with white fondant.",
                        "Sure! For a 3-tier wedding cake the starting price is KES 15,000.",
                        "That sounds great. Can I see some samples?",
                        "Of course! Check our portfolio for recent designs.",
                        "How many days notice do you need for a custom order?",
                        "We typically need at least 5 days for custom orders.",
                    ])
                )
                msg = Message(
                    conversation_id=conv.id,
                    sender_type=sender_type,
                    sender_name=customer_name if sender_type == "CUSTOMER" else user.name,
                    sender_id=None if sender_type == "CUSTOMER" else user.id,
                    content=content,
                    is_read=True if j < msg_count - 1 else random.random() < 0.5,
                    created_at=msg_time,
                )
                session.add(msg)
                msg_time += timedelta(minutes=random.randint(5, 120))

        print(f"  ✓ {bakery.name}: {conv_count} conversations")


async def seed_notifications(session: AsyncSession, admin: User, bakery_pairs: list[tuple[User, Bakery]]):
    print("Seeding notifications...")
    now = datetime.now(timezone.utc)

    # Check if admin already has notifications
    existing = await session.scalar(
        select(Notification).where(Notification.user_id == admin.id)
    )
    if existing:
        print("  — Notifications already exist")
        return

    # Admin notifications
    admin_notifications = [
        {"type": "NEW_BAKER", "title": "New baker registration", "body": "Petal & Icing Cakes has applied to join the platform.", "link": "/admin/dashboard/bakeries"},
        {"type": "ORDER_ALERT", "title": "High order volume", "body": "Sweet Crumbs Bakery has received 10+ orders today.", "link": "/admin/dashboard"},
        {"type": "REVIEW_ALERT", "title": "New 1-star review", "body": "A customer left a 1-star review for The Frosted Oven.", "link": "/admin/dashboard/bakeries"},
    ]
    for n in admin_notifications:
        notif = Notification(
            user_id=admin.id,
            type=n["type"],
            title=n["title"],
            body=n["body"],
            link=n["link"],
            is_read=random.random() < 0.4,
            created_at=random_date(now - timedelta(days=7), now),
        )
        session.add(notif)

    # Baker notifications
    for user, bakery in bakery_pairs[:5]:
        baker_notifications = [
            {"type": "NEW_ORDER", "title": "New order received!", "body": f"You have a new order for {bakery.name}.", "link": "/baker/dashboard/orders"},
            {"type": "ORDER_COMPLETED", "title": "Order completed", "body": "Order has been marked as completed.", "link": "/baker/dashboard/orders"},
        ]
        for n in baker_notifications:
            notif = Notification(
                user_id=user.id,
                type=n["type"],
                title=n["title"],
                body=n["body"],
                link=n["link"],
                is_read=random.random() < 0.5,
                created_at=random_date(now - timedelta(days=14), now),
            )
            session.add(notif)

    print("  ✓ Notifications seeded for admin and bakers")


# ──────────────────────────────── Main

async def main():
    print("=" * 60)
    print("  Crumbly Backend — Database Seeder")
    print("=" * 60)
    print()

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        async with session.begin():
            cat_map = await seed_categories(session)
            admin = await seed_super_admin(session)
            bakery_pairs = await seed_bakeries_and_users(session)
            all_cakes = await seed_cakes(session, bakery_pairs, cat_map)
            await seed_portfolio(session, bakery_pairs)
            all_orders = await seed_orders(session, bakery_pairs, all_cakes)
            await seed_reviews(session, bakery_pairs)
            await seed_conversations_and_messages(session, bakery_pairs)
            await seed_notifications(session, admin, bakery_pairs)

    print()
    print("=" * 60)
    print("  Seeding complete!")
    print()
    print(f"  Admin email:  {SUPER_ADMIN_EMAIL} (invited — setup link dispatched)")
    print(f"  Baker login:  jane@sweetcrumbs.co.ke (configured via env)")
    print("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
