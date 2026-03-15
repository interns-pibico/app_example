from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.services.user import UserService

security_scheme = HTTPBearer()


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_service = UserService(session)

    async def authenticate(self, email: str, password: str) -> TokenResponse:
        user = await self.user_service.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("User account is disabled")
        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise AuthenticationError("Invalid token type")
            user_id = payload.get("sub")
            if user_id is None:
                raise AuthenticationError("Invalid token")
        except JWTError:
            raise AuthenticationError("Invalid or expired refresh token")

        user = await self.user_service.get_by_id(int(user_id))
        if not user.is_active:
            raise AuthenticationError("User account is disabled")

        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
        )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")
        user_id = payload.get("sub")
        if user_id is None:
            raise AuthenticationError("Invalid token")
    except JWTError:
        raise AuthenticationError("Invalid or expired token")

    user_service = UserService(session)
    user = await user_service.get_by_id(int(user_id))
    if not user.is_active:
        raise AuthenticationError("User account is disabled")
    return user
