from pydantic import BaseModel, field_validator


class CategoryCreate(BaseModel):
    name: str
    icon: str = "cake"

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, name: str) -> str:
        if not name or not name.strip():
            raise ValueError("Name is required")
        return name.strip()


class CategoryUpdate(CategoryCreate):
    pass


class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    icon: str

    model_config = {"from_attributes": True}
