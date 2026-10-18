"""Pydantic schemas package for Crumbly.

Exports all request and response schemas across all application domains.
"""

from app.schemas.admin import (
    AdminBakeryCounts,
    AdminBakeryOwner,
    AdminBakeryResponse,
    AdminBakeryUpdate,
    AdminInviteRequest,
    AdminUserResponse,
)
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterBakerRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.bakery import (
    BakeryListItem,
    BakeryResponse,
    BakerySettingsUpdate,
)
from app.schemas.cake import (
    CakeBakery,
    CakeCreate,
    CakeResponse,
    CakeUpdate,
    SizeOption,
)
from app.schemas.category import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
)
from app.schemas.messaging import (
    ConversationCreate,
    ConversationResponse,
    CustomerConversationCreate,
    MessageCreate,
    MessageResponse,
    TypingStatusResponse,
    TypingStatusUpdate,
)
from app.schemas.notification import (
    NotificationResponse,
)
from app.schemas.order import (
    BakeryBasic,
    OrderCreate,
    OrderItemInput,
    OrderResponse,
    OrderUpdate,
)
from app.schemas.portfolio import (
    PortfolioItemCreate,
    PortfolioItemResponse,
)

__all__ = [
    # Admin
    "AdminBakeryCounts",
    "AdminBakeryOwner",
    "AdminBakeryResponse",
    "AdminBakeryUpdate",
    "AdminInviteRequest",
    "AdminUserResponse",
    # Auth
    "ForgotPasswordRequest",
    "LoginRequest",
    "RegisterBakerRequest",
    "ResetPasswordRequest",
    "TokenResponse",
    "UserResponse",
    # Bakery
    "BakeryListItem",
    "BakeryResponse",
    "BakerySettingsUpdate",
    # Cake
    "CakeBakery",
    "CakeCreate",
    "CakeResponse",
    "CakeUpdate",
    "SizeOption",
    # Category
    "CategoryCreate",
    "CategoryResponse",
    "CategoryUpdate",
    # Messaging
    "ConversationCreate",
    "ConversationResponse",
    "CustomerConversationCreate",
    "MessageCreate",
    "MessageResponse",
    "TypingStatusResponse",
    "TypingStatusUpdate",
    # Notification
    "NotificationResponse",
    # Order
    "BakeryBasic",
    "OrderCreate",
    "OrderItemInput",
    "OrderResponse",
    "OrderUpdate",
    # Portfolio
    "PortfolioItemCreate",
    "PortfolioItemResponse",
]
