from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid, utcnow
from app.models.enums import Role

if TYPE_CHECKING:
    from app.models.bakery import Bakery
    from app.models.notification import Notification


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    passwordHash: Mapped[str] = mapped_column("passwordHash", String, nullable=False)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(
        Enum("SUPER_ADMIN", "BAKER", name="Role", create_type=False),
        nullable=False,
        default=Role.BAKER.value,
    )
    isDeleted: Mapped[bool] = mapped_column("isDeleted", Boolean, default=False)
    deletedAt: Mapped[datetime | None] = mapped_column("deletedAt", DateTime(timezone=True), nullable=True)
    createdAt: Mapped[datetime] = mapped_column("createdAt", DateTime(timezone=True), default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    bakery: Mapped["Bakery | None"] = relationship("Bakery", back_populates="owner", uselist=False)
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="user")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String, nullable=False)
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    expiresAt: Mapped[datetime] = mapped_column("expiresAt", DateTime(timezone=True), nullable=False)
    createdAt: Mapped[datetime] = mapped_column("createdAt", DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("password_reset_tokens_email_idx", "email"),)
