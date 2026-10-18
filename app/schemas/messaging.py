from datetime import datetime
from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    sender_name: str | None = None  # Needed for anonymous customers


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_type: str
    sender_id: str | None = None
    sender_name: str
    content: str
    is_read: bool
    created_at: datetime | str

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    bakery_id: str | None = None
    subject: str
    message: str | None = None


class ConversationResponse(BaseModel):
    id: str
    order_id: str | None = None
    bakery_id: str
    customer_token: str | None = None
    subject: str | None = None
    is_closed: bool
    created_at: datetime | str
    updated_at: datetime | str

    messages: list[MessageResponse] = []
    
    # Include order details if related
    customerName: str | None = None
    orderTotalAmount: int | None = None
    bakeryName: str | None = None
    bakerySlug: str | None = None
    lastMessage: str | None = None
    unreadCount: int = 0
    is_typing: bool = False
    typing_user: str | None = None

    model_config = {"from_attributes": True}


class CustomerConversationCreate(BaseModel):
    bakery_id: str
    subject: str = "Customer Inquiry"
    initial_message: str | None = None
    message: str | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None


class TypingStatusUpdate(BaseModel):
    is_typing: bool = True


class TypingStatusResponse(BaseModel):
    is_typing: bool
    sender_type: str | None = None
    sender_name: str | None = None


