"""Auth API schemas — never include password hashes or secrets."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.models import Role, UserStatus


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
    full_name: str | None = None
    status: UserStatus = UserStatus.ACTIVE


class RegisterResponse(BaseModel):
    message: str
    user: UserPublic


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class InviteUserRequest(BaseModel):
    """Admin invite body. organization_id from the client is ignored."""

    model_config = ConfigDict(extra="ignore")

    full_name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=3)
    role: Role
    employee_id: str | None = None

    @field_validator("employee_id")
    @classmethod
    def employee_id_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().upper()
        return cleaned or None

    @field_validator("full_name")
    @classmethod
    def required_name(cls, value: str) -> str:
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


class PatchUserRequest(BaseModel):
    """Admin user update. organization_id and user identity from the body are ignored."""

    model_config = ConfigDict(extra="ignore")

    role: Role | None = None
    employee_id: str | None = None

    @field_validator("employee_id")
    @classmethod
    def employee_id_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().upper()
        return cleaned or None


class ActivateAccountRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    token: str = Field(..., min_length=8)
    password: str = Field(..., min_length=1)
    confirm_password: str = Field(..., min_length=1)

    @field_validator("token")
    @classmethod
    def token_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must be a non-empty string")
        return cleaned


class InvitationInfo(BaseModel):
    expires_at: str
    activation_path: str
    activation_token: str


class ManagedUserPublic(BaseModel):
    user_id: str
    username: str
    full_name: str | None = None
    organization_id: str
    role: Role
    employee_id: str | None = None
    status: UserStatus
    is_active: bool
    created_at: str | None = None


class UserListResponse(BaseModel):
    users: list[ManagedUserPublic]
    total: int
    limit: int
    offset: int


class InviteUserResponse(BaseModel):
    message: str
    user: ManagedUserPublic
    invitation: InvitationInfo


class DirectoryEmployee(BaseModel):
    employee_id: str
    name: str
    department: str | None = None
    job_role: str | None = None
    employment_status: str | None = None
    bound_user_id: str | None = None
    bound_username: str | None = None
    available: bool = True


class EmployeeDirectoryResponse(BaseModel):
    employees: list[DirectoryEmployee]
