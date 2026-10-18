"""Admin domain schemas for requests and responses."""

from pydantic import BaseModel
from app.schemas.bakery import AdminBakeryUpdate


class AdminBakeryOwner(BaseModel):
    id: str
    email: str
    name: str
    phone: str | None = None


class AdminBakeryCounts(BaseModel):
    cakes: int = 0
    orders: int = 0


class AdminBakeryResponse(BaseModel):
    id: str
    name: str
    slug: str
    city: str
    address: str | None = None
    whatsappNumber: str
    mpesaTillNumber: str | None = None
    description: str | None = None
    status: str
    isDeleted: bool
    deletedAt: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None
    email: str | None = None
    owner: AdminBakeryOwner | None = None
    _count: AdminBakeryCounts = AdminBakeryCounts()

    model_config = {"from_attributes": True}


class AdminInviteRequest(BaseModel):
    email: str
    name: str = "Administrator"


class AdminUserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    createdAt: str | None = None
    isPendingInvite: bool = False


__all__ = [
    "AdminBakeryUpdate",
    "AdminBakeryOwner",
    "AdminBakeryCounts",
    "AdminBakeryResponse",
    "AdminInviteRequest",
    "AdminUserResponse",
]
