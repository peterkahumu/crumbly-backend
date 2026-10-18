import enum


class Role(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    BAKER = "BAKER"


class BakeryStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONTACTED = "CONTACTED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class OrderChannel(str, enum.Enum):
    WHATSAPP = "WHATSAPP"
    MPESA = "MPESA"


class SenderType(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    BAKER = "BAKER"
    ADMIN = "ADMIN"
