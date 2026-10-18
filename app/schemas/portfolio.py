from datetime import datetime
from pydantic import BaseModel, field_validator


class PortfolioItemCreate(BaseModel):
    imageUrl: str
    caption: str | None = None
    eventType: str | None = None

    @field_validator("imageUrl")
    @classmethod
    def url_not_empty(cls, imageUrl: str) -> str:
        if not imageUrl or not imageUrl.strip():
            raise ValueError("Add an image")
        return imageUrl.strip()


class PortfolioItemResponse(BaseModel):
    id: str
    bakeryId: str
    imageUrl: str
    caption: str | None = None
    eventType: str | None = None
    createdAt: datetime

    model_config = {"from_attributes": True}
