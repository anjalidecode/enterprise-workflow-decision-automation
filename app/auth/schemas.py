"""Auth API schemas — never include password hashes or secrets."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.models import Role


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)

    @field_validator("username")
    @classmethod
    def username_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must be a non-empty string")
        return cleaned

    @field_validator("password")
    @classmethod
    def password_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("must be a non-empty string")
        return value


class RegisterRequest(BaseModel):
    """Public registration body.

    Role, organization_id, employee_id, and user_role are ignored if present.
    Privileged roles cannot be self-selected from the client.
    """

    model_config = ConfigDict(extra="ignore")

    full_name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)
    confirm_password: str = Field(..., min_length=1)
    organization_name: str = Field(..., min_length=1)

    @field_validator("full_name", "organization_name")
    @classmethod
    def required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must be a non-empty string")
        return cleaned

    @field_validator("email")
    @classmethod
    def email_not_blank(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("must be a non-empty string")
        return cleaned


class UserPublic(BaseModel):
    user_id: str
    username: str
    organization_id: str
    role: Role
    employee_id: str | None = None


class RegisterResponse(BaseModel):
    message: str
    user: UserPublic


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic
