from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid, utcnow

if TYPE_CHECKING:
    from app.models.bakery import Bakery


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    icon: Mapped[str] = mapped_column(String, nullable=False, default="cake")

    cakes: Mapped[list["Cake"]] = relationship("Cake", back_populates="category")


class Cake(Base):
    __tablename__ = "cakes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    bakeryId: Mapped[str] = mapped_column("bakeryId", String, ForeignKey("bakeries.id", ondelete="CASCADE"))
    categoryId: Mapped[str] = mapped_column("categoryId", String, ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    discountPrice: Mapped[int | None] = mapped_column("discountPrice", Integer, nullable=True)
    images: Mapped[list[str]] = mapped_column(
        ARRAY(String).with_variant(JSON, "sqlite"), nullable=False, default=list
    )
    sizeOptions: Mapped[dict | None] = mapped_column(
        "sizeOptions", JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    isAvailable: Mapped[bool] = mapped_column("isAvailable", Boolean, default=True)
    isFeatured: Mapped[bool] = mapped_column("isFeatured", Boolean, default=False)
    createdAt: Mapped[datetime] = mapped_column("createdAt", DateTime(timezone=True), default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    bakery: Mapped["Bakery"] = relationship("Bakery", back_populates="cakes")
    category: Mapped["Category"] = relationship("Category", back_populates="cakes")

    __table_args__ = (
        UniqueConstraint("bakeryId", "slug", name="cakes_bakeryId_slug_key"),
        Index("cakes_categoryId_idx", "categoryId"),
        Index("cakes_bakeryId_idx", "bakeryId"),
    )
