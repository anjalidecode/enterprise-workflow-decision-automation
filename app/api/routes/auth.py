"""Authentication routes: login and current user."""

from __future__ import annotations

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser
from app.auth.schemas import LoginRequest, TokenResponse, UserPublic
from app.auth.service import login, to_public_user

router = APIRouter(tags=["Auth"])


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Login and obtain a JWT access token",
    description=(
        "Authenticates against the temporary development user store. "
        "Returns a Bearer access token. Never returns password hashes or secrets."
    ),
)
def login_endpoint(body: LoginRequest) -> TokenResponse:
    return login(body.username, body.password)


@router.get(
    "/auth/me",
    response_model=UserPublic,
    summary="Current authenticated user",
    description="Requires Authorization: Bearer <access_token>.",
)
def me(user: CurrentUser) -> UserPublic:
    return to_public_user(user)
