from datetime import datetime
from pydantic import BaseModel


class BakerySettingsUpdate(BaseModel):
    name: str
    description: str | None = None
    city: str
    address: str | None = None
    whatsappNumber: str
    mpesaTillNumber: str | None = None
    logoUrl: str | None = None
    coverImageUrl: str | None = None
    newPassword: str | None = None


class BakeryResponse(BaseModel):
    id: str
    ownerId: str
    slug: str
    name: str
    description: str | None = None
    logoUrl: str | None = None
    coverImageUrl: str | None = None
    whatsappNumber: str
    mpesaTillNumber: str | None = None
    city: str
    address: str | None = None
    status: str
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}


class BakeryListItem(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None = None
    logoUrl: str | None = None
    coverImageUrl: str | None = None
    city: str
    status: str
    createdAt: datetime
    cake_count: int = 0

    model_config = {"from_attributes": True}


class AdminBakeryUpdate(BaseModel):
    status: str | None = None
    name: str | None = None
    email: str | None = None
    city: str | None = None
    address: str | None = None
    whatsappNumber: str | None = None
    mpesaTillNumber: str | None = None
    description: str | None = None
    password: str | None = None
    isDeleted: bool | None = None

