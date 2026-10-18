from datetime import datetime
from pydantic import BaseModel, field_validator


class OrderItemInput(BaseModel):
    cakeId: str
    name: str
    price: int
    qty: int


class OrderCreate(BaseModel):
    bakeryId: str
    customerName: str
    customerPhone: str
    items: list[OrderItemInput]

    @field_validator("customerName")
    @classmethod
    def name_not_empty(cls, customerName: str) -> str:
        if not customerName or not customerName.strip():
            raise ValueError("Enter your name")
        return customerName.strip()

    @field_validator("customerPhone")
    @classmethod
    def phone_not_empty(cls, customerPhone: str) -> str:
        if not customerPhone or not customerPhone.strip():
            raise ValueError("Enter a valid phone number")
        return customerPhone.strip()

    @field_validator("items")
    @classmethod
    def items_not_empty(cls, items: list) -> list:
        if not items:
            raise ValueError("Your cart is empty")
        return items


class OrderUpdate(BaseModel):
    status: str | None = None
    customerName: str | None = None
    customerPhone: str | None = None
    totalAmount: int | None = None
    mpesaReceiptNumber: str | None = None


class BakeryBasic(BaseModel):
    id: str
    name: str
    slug: str

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: str
    bakeryId: str
    customerName: str
    customerPhone: str
    items: list[dict] | dict
    totalAmount: int
    status: str
    channel: str
    mpesaReceiptNumber: str | None = None
    createdAt: datetime
    updatedAt: datetime
    bakery: BakeryBasic | None = None
    conversationToken: str | None = None

    model_config = {"from_attributes": True}
