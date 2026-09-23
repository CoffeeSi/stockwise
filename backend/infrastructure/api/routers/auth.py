"""Local employee login. Only an administrator can provision buyers."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.domain.entities.catalog import User
from backend.domain.enums import UserRole
from backend.infrastructure.api import dependencies as deps
from backend.infrastructure.api.schemas.auth import (
    CreateBuyerRequest, LoginRequest, RoleRequest, StaffResponse, TokenResponse,
)
from backend.infrastructure.auth_security import hash_password, issue_access_token, verify_password
from backend.infrastructure.persistence.models.catalog import UserCredentialModel, UserModel

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _staff(account: UserModel | User) -> StaffResponse:
    return StaffResponse(id=account.id, username=account.external_id,
                         display_name=account.display_name, role=account.role)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request) -> TokenResponse:
    settings = request.app.state.settings
    if settings.jwt_secret is None:
        raise HTTPException(503, detail={"code": "auth_not_configured"})
    unauthorized = HTTPException(401, detail={"code": "invalid_credentials"},
                                 headers={"WWW-Authenticate": "Bearer"})
    with request.app.state.database.session() as session:
        account = session.scalar(select(UserModel).where(UserModel.external_id == body.username.strip().lower()))
        credentials = session.get(UserCredentialModel, account.id) if account else None
        if not account or not credentials or not account.is_active:
            raise unauthorized
        if not verify_password(credentials.password_hash, body.password):
            raise unauthorized
        token, lifetime = issue_access_token(account.id, credentials.token_version,
                                             settings.jwt_secret.get_secret_value(), settings.jwt_access_minutes)
    return TokenResponse(access_token=token, expires_in=lifetime)


@router.get("/me", response_model=StaffResponse)
def me(user: User = Depends(deps.get_current_user)) -> StaffResponse:
    return _staff(user)


def _create_account(body: CreateBuyerRequest, request: Request, role: UserRole) -> StaffResponse:
    account = UserModel(external_id=body.username.strip().lower(),
                        display_name=body.display_name.strip(), role=role)
    password_hash = hash_password(body.password)
    try:
        with request.app.state.database.session() as session:
            session.add(account)
            session.flush()
            session.add(UserCredentialModel(user_id=account.id, password_hash=password_hash))
            session.flush()
            result = _staff(account)
    except IntegrityError:
        raise HTTPException(409, detail={"code": "username_taken"}) from None
    return result


@router.post("/register", response_model=StaffResponse, status_code=201)
def register(body: CreateBuyerRequest, request: Request) -> StaffResponse:
    """Self-registration grants read access; only an administrator can elevate it."""
    return _create_account(body, request, UserRole.VIEWER)


@router.post("/users", response_model=StaffResponse, status_code=201)
def create_buyer(body: CreateBuyerRequest, request: Request,
                 _admin: User = Depends(deps.require_admin)) -> StaffResponse:
    return _create_account(body, request, UserRole.BUYER)


@router.get("/users", response_model=list[StaffResponse])
def list_users(request: Request, limit: int = Query(default=50, ge=1, le=100),
               offset: int = Query(default=0, ge=0),
               _admin: User = Depends(deps.require_admin)):
    with request.app.state.database.session() as session:
        accounts = session.scalars(select(UserModel).join(UserCredentialModel)
                                  .order_by(UserModel.created_at, UserModel.id).offset(offset).limit(limit))
        return [_staff(account) for account in accounts]


@router.patch("/users/{user_id}/role", response_model=StaffResponse)
def update_role(user_id: UUID, body: RoleRequest, request: Request,
                admin: User = Depends(deps.require_admin)):
    if user_id == admin.id:
        raise HTTPException(409, detail={"code": "self_role_change_forbidden"})
    with request.app.state.database.session() as session:
        account = session.get(UserModel, user_id)
        if account is None:
            raise HTTPException(404, detail={"code": "not_found"})
        account.role = body.role
        return _staff(account)


@router.post("/logout", status_code=204)
def logout(request: Request, user: User = Depends(deps.get_current_user)):
    with request.app.state.database.session() as session:
        credentials = session.get(UserCredentialModel, user.id, with_for_update=True)
        if credentials is not None:
            credentials.token_version += 1
    return Response(status_code=204)
