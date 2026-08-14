"""Authentication routes: login and current user."""

from __future__ import annotations

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser
from app.auth.schemas import (
    ActivateAccountRequest,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserPublic,
)
from app.auth.service import login, register, to_public_user
from app.auth.user_admin import complete_invitation

router = APIRouter(tags=["Auth"])


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Login and obtain a JWT access token",
    description=(
        "Authenticates against PostgreSQL users. "
        "Returns a Bearer access token. Never returns password hashes or secrets."
    ),
)
def login_endpoint(body: LoginRequest) -> TokenResponse:
    return login(body.username, body.password)


@router.post(
    "/auth/register",
    response_model=RegisterResponse,
    summary="Register a new organization account",
    description=(
        "Creates a PostgreSQL user with a bcrypt password hash. "
        "Role and organization identity are assigned by the server. "
        "The first user of a newly created organization becomes its administrator; "
        "subsequent public registrations for an existing organization receive the employee role. "
        "Never returns password hashes or secrets."
    ),
)
def register_endpoint(body: RegisterRequest) -> RegisterResponse:
    return register(
        full_name=body.full_name,
        email=body.email,
        password=body.password,
        confirm_password=body.confirm_password,
        organization_name=body.organization_name,
    )


@router.post(
    "/auth/activate",
    response_model=RegisterResponse,
    summary="Activate an invited account",
    description=(
        "Consumes a one-time invitation token and sets a password. "
        "Does not accept role or organization_id from the client."
    ),
)
def activate_account_endpoint(body: ActivateAccountRequest) -> RegisterResponse:
    user = complete_invitation(
        token=body.token,
        password=body.password,
        confirm_password=body.confirm_password,
    )
    return RegisterResponse(
        message="Account activated successfully. You can now sign in.",
        user=UserPublic(
            user_id=user.user_id,
            username=user.username,
            organization_id=user.organization_id,
            role=user.role,
            employee_id=user.employee_id,
            full_name=user.full_name,
            status=user.status,
        ),
    )


@router.get(
    "/auth/me",
    response_model=UserPublic,
    summary="Current authenticated user",
    description="Requires Authorization: Bearer <access_token>.",
)
def me(user: CurrentUser) -> UserPublic:
    return to_public_user(user)
