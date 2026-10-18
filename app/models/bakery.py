from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid, utcnow
from app.models.enums import BakeryStatus

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.cake import Cake
    from app.models.order import Order, Review
    from app.models.messaging import Conversation


class Bakery(Base):
    __tablename__ = "bakeries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    ownerId: Mapped[str] = mapped_column("ownerId", String, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    logoUrl: Mapped[str | None] = mapped_column("logoUrl", String, nullable=True)
    coverImageUrl: Mapped[str | None] = mapped_column("coverImageUrl", String, nullable=True)
    whatsappNumber: Mapped[str] = mapped_column("whatsappNumber", String, nullable=False)
    mpesaTillNumber: Mapped[str | None] = mapped_column("mpesaTillNumber", String, nullable=True)
    city: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("PENDING", "APPROVED", "SUSPENDED", "DELETED", name="BakeryStatus", create_type=False),
        nullable=False,
        default=BakeryStatus.PENDING.value,
    )
    isDeleted: Mapped[bool] = mapped_column("isDeleted", Boolean, default=False)
    deletedAt: Mapped[datetime | None] = mapped_column("deletedAt", DateTime(timezone=True), nullable=True)
    createdAt: Mapped[datetime] = mapped_column("createdAt", DateTime(timezone=True), default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    owner: Mapped["User"] = relationship("User", back_populates="bakery")
    cakes: Mapped[list["Cake"]] = relationship("Cake", back_populates="bakery", cascade="all, delete-orphan")
    portfolio: Mapped[list["PortfolioItem"]] = relationship(
        "PortfolioItem", back_populates="bakery", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="bakery", cascade="all, delete-orphan")
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="bakery", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="bakery", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("bakeries_status_idx", "status"),
        Index("bakeries_isDeleted_idx", "isDeleted"),
        Index("bakeries_city_idx", "city"),
    )


class PortfolioItem(Base):
    __tablename__ = "portfolio_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    bakeryId: Mapped[str] = mapped_column("bakeryId", String, ForeignKey("bakeries.id", ondelete="CASCADE"))
    imageUrl: Mapped[str] = mapped_column("imageUrl", String, nullable=False)
    caption: Mapped[str | None] = mapped_column(String, nullable=True)
    eventType: Mapped[str | None] = mapped_column("eventType", String, nullable=True)
    createdAt: Mapped[datetime] = mapped_column("createdAt", DateTime(timezone=True), default=utcnow)

    bakery: Mapped["Bakery"] = relationship("Bakery", back_populates="portfolio")

    __table_args__ = (Index("portfolio_items_bakeryId_idx", "bakeryId"),)
