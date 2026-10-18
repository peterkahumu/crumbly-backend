import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


def generate_uuid() -> str:
    """Generate a standard canonical UUID4 string."""
    return str(uuid.uuid4())


# Backwards compatibility alias
generate_id = generate_uuid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass
