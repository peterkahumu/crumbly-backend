from datetime import datetime
from pydantic import BaseModel, field_validator


class SizeOption(BaseModel):
    label: str
    priceModifier: int = 0


class CakeCreate(BaseModel):
    name: str
    categoryId: str
    description: str | None = None
    price: int
    discountPrice: int | None = None
    images: list[str]
    sizeOptions: list[SizeOption] = []
    isAvailable: bool = True
    isFeatured: bool = False

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, name: str) -> str:
        if not name or not name.strip():
            raise ValueError("Name is required")
        return name.strip()

    @field_validator("images")
    @classmethod
    def at_least_one_image(cls, images: list[str]) -> list[str]:
        if not images:
            raise ValueError("Add at least one image")
        return images

    @field_validator("price")
    @classmethod
    def price_positive(cls, price: int) -> int:
        if price <= 0:
            raise ValueError("Price must be a positive number")
        return price


class CakeUpdate(BaseModel):
    name: str | None = None
    categoryId: str | None = None
    description: str | None = None
    price: int | None = None
    discountPrice: int | None = None
    images: list[str] | None = None
    sizeOptions: list[SizeOption] | None = None
    isAvailable: bool | None = None
    isFeatured: bool | None = None


class CakeBakery(BaseModel):
    name: str
    slug: str

    model_config = {"from_attributes": True}


class CakeCategory(BaseModel):
    id: str
    name: str
    slug: str

    model_config = {"from_attributes": True}


class CakeResponse(BaseModel):
    id: str
    bakeryId: str
    categoryId: str
    name: str
    slug: str
    description: str | None = None
    price: int
    discountPrice: int | None = None
    images: list[str]
    sizeOptions: list[dict] | None = None
    isAvailable: bool
    isFeatured: bool
    createdAt: datetime
    updatedAt: datetime
    bakery: CakeBakery | None = None
    category: CakeCategory | None = None

    model_config = {"from_attributes": True}
