from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid, utcnow
from app.models.enums import OrderChannel, OrderStatus

if TYPE_CHECKING:
    from app.models.bakery import Bakery
    from app.models.messaging import Conversation


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    bakeryId: Mapped[str] = mapped_column("bakeryId", String, ForeignKey("bakeries.id", ondelete="CASCADE"))
    customerName: Mapped[str] = mapped_column("customerName", String, nullable=False)
    customerPhone: Mapped[str] = mapped_column("customerPhone", String, nullable=False)
    items: Mapped[dict] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=False)
    totalAmount: Mapped[int] = mapped_column("totalAmount", Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("PENDING", "CONTACTED", "CONFIRMED", "COMPLETED", "CANCELLED", name="OrderStatus", create_type=False),
        nullable=False,
        default=OrderStatus.PENDING.value,
    )
    channel: Mapped[str] = mapped_column(
        Enum("WHATSAPP", "MPESA", name="OrderChannel", create_type=False),
        nullable=False,
        default=OrderChannel.WHATSAPP.value,
    )
    mpesaReceiptNumber: Mapped[str | None] = mapped_column("mpesaReceiptNumber", String, nullable=True)
    createdAt: Mapped[datetime] = mapped_column("createdAt", DateTime(timezone=True), default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    bakery: Mapped["Bakery"] = relationship("Bakery", back_populates="orders")
    conversation: Mapped["Conversation | None"] = relationship("Conversation", back_populates="order", uselist=False)

    __table_args__ = (
        Index("orders_bakeryId_idx", "bakeryId"),
        Index("orders_status_idx", "status"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    bakeryId: Mapped[str] = mapped_column("bakeryId", String, ForeignKey("bakeries.id", ondelete="CASCADE"))
    customerName: Mapped[str] = mapped_column("customerName", String, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
    createdAt: Mapped[datetime] = mapped_column("createdAt", DateTime(timezone=True), default=utcnow)

    bakery: Mapped["Bakery"] = relationship("Bakery", back_populates="reviews")

    __table_args__ = (Index("reviews_bakeryId_idx", "bakeryId"),)
