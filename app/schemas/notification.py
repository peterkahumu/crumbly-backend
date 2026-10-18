from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    body: str | None = None
    link: str | None = None
    is_read: bool
    metadata_: dict | None = None
    created_at: str

    model_config = {"from_attributes": True, "populate_by_name": True}
