"""Authenticated user-management routes. Organization is taken from the JWT user."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import require_admin
from app.auth.models import User
from app.auth.schemas import (
    EmployeeDirectoryResponse,
    InviteUserRequest,
    InviteUserResponse,
    ManagedUserPublic,
    PatchUserRequest,
    UserListResponse,
)
from app.auth.user_admin import (
    activate_user,
    deactivate_user,
    get_user,
    invite_user,
    list_employees,
    list_users,
    patch_user,
)

router = APIRouter(tags=["Users"])
AdminUser = Annotated[User, Depends(require_admin)]


@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List users in the current organization",
)
def list_users_endpoint(
    admin: AdminUser,
    search: str | None = Query(default=None),
    role: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> UserListResponse:
    return list_users(
        admin,
        search=search,
        role=role,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/employees",
    response_model=EmployeeDirectoryResponse,
    summary="List organization employee records available for account binding",
)
def list_employees_endpoint(admin: AdminUser) -> EmployeeDirectoryResponse:
    return list_employees(admin)


@router.post(
    "/users/invite",
    response_model=InviteUserResponse,
    summary="Invite a user to the current organization",
)
def invite_user_endpoint(admin: AdminUser, body: InviteUserRequest) -> InviteUserResponse:
    return invite_user(
        admin,
        full_name=body.full_name,
        email=body.email,
        role=body.role,
        employee_id=body.employee_id,
    )


@router.get(
    "/users/{user_id}",
    response_model=ManagedUserPublic,
    summary="Get an organization user",
)
def get_user_endpoint(admin: AdminUser, user_id: str) -> ManagedUserPublic:
    return get_user(admin, user_id)


@router.patch(
    "/users/{user_id}",
    response_model=ManagedUserPublic,
    summary="Update an organization user's role or employee binding",
)
def patch_user_endpoint(
    admin: AdminUser,
    user_id: str,
    body: PatchUserRequest,
) -> ManagedUserPublic:
    return patch_user(admin, user_id, role=body.role, employee_id=body.employee_id)


@router.post(
    "/users/{user_id}/activate",
    response_model=ManagedUserPublic,
    summary="Reactivate a deactivated organization user",
)
def activate_user_endpoint(admin: AdminUser, user_id: str) -> ManagedUserPublic:
    return activate_user(admin, user_id)


@router.post(
    "/users/{user_id}/deactivate",
    response_model=ManagedUserPublic,
    summary="Deactivate an organization user",
)
def deactivate_user_endpoint(admin: AdminUser, user_id: str) -> ManagedUserPublic:
    return deactivate_user(admin, user_id)
