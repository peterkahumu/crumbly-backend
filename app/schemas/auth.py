from pydantic import BaseModel, field_validator


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class RegisterBakerRequest(BaseModel):
    name: str
    email: str
    password: str
    phone: str | None = None
    bakeryName: str
    city: str
    whatsappNumber: str
    description: str | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, email: str) -> str:
        return email.strip().lower()

    @field_validator("name", "bakeryName", "city", "whatsappNumber")
    @classmethod
    def not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("This field is required")
        return value.strip()

    @field_validator("password")
    @classmethod
    def min_length(cls, password: str) -> str:
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters")
        return password


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def min_length(cls, password: str) -> str:
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters")
        return password


class TokenResponse(BaseModel):
    user: dict
    token: str


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    bakeryId: str | None = None
    bakerySlug: str | None = None
    bakeryStatus: str | None = None

    model_config = {"from_attributes": True}
