"""SQLAlchemy ORM models package.

All models and enums are exported here for backward-compatible imports
via `from app.models import ...`.
"""

from app.models.base import Base, generate_id, generate_uuid, utcnow
from app.models.enums import (
    Role,
    BakeryStatus,
    OrderStatus,
    OrderChannel,
    SenderType,
)
from app.models.user import User, PasswordResetToken
from app.models.bakery import Bakery, PortfolioItem
from app.models.cake import Category, Cake
from app.models.order import Order, Review
from app.models.messaging import Conversation, Message
from app.models.notification import Notification

__all__ = [
    "Base",
    "generate_id",
    "generate_uuid",
    "utcnow",
    "Role",
    "BakeryStatus",
    "OrderStatus",
    "OrderChannel",
    "SenderType",
    "User",
    "PasswordResetToken",
    "Bakery",
    "PortfolioItem",
    "Category",
    "Cake",
    "Order",
    "Review",
    "Conversation",
    "Message",
    "Notification",
]
