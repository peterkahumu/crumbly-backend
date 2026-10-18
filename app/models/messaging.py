from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid, utcnow

if TYPE_CHECKING:
    from app.models.bakery import Bakery
    from app.models.order import Order


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    order_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    bakery_id: Mapped[str] = mapped_column(
        String, ForeignKey("bakeries.id", ondelete="CASCADE"), nullable=False
    )
    customer_token: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    order: Mapped["Order | None"] = relationship("Order", back_populates="conversation")
    bakery: Mapped["Bakery"] = relationship("Bakery", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )

    __table_args__ = (
        Index("idx_conversations_bakery", "bakery_id"),
        Index("idx_conversations_order", "order_id"),
        Index("idx_conversations_token", "customer_token"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sender_type: Mapped[str] = mapped_column(String, nullable=False)
    sender_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sender_name: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("idx_messages_conversation", "conversation_id"),
        Index("idx_messages_created", "created_at"),
    )
