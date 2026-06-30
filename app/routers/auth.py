"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.dependencies import CurrentUser, DatabaseDep, SettingsDep
from app.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth import AuthService, AuthTokens

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    payload: UserRegisterRequest,
    db: DatabaseDep,
    settings: SettingsDep,
) -> TokenResponse:
    tokens = await AuthService(db, settings).register_user(
        email=str(payload.email),
        password=payload.password,
    )
    return _token_response(tokens)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Log in with email and password",
)
async def login(
    payload: UserLoginRequest,
    db: DatabaseDep,
    settings: SettingsDep,
) -> TokenResponse:
    tokens = await AuthService(db, settings).login(
        email=str(payload.email),
        password=payload.password,
    )
    return _token_response(tokens)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh an access token",
)
async def refresh(
    payload: RefreshTokenRequest,
    db: DatabaseDep,
    settings: SettingsDep,
) -> TokenResponse:
    access_token = await AuthService(db, settings).refresh_access_token(payload.refresh_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=payload.refresh_token,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Return the authenticated user",
)
async def me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


def _token_response(tokens: AuthTokens) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )
