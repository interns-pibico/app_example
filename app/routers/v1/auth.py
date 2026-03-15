from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserRead
from app.services.auth import AuthService
from app.services.user import UserService

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/register", response_model=UserRead, status_code=201)
async def register(data: RegisterRequest, session: DbSession):
    from app.schemas.user import UserCreate

    user_service = UserService(session)
    user = await user_service.create(
        UserCreate(
            email=data.email,
            username=data.username,
            password=data.password,
            full_name=data.full_name,
        )
    )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, session: DbSession):
    auth_service = AuthService(session)
    return await auth_service.authenticate(data.email, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, session: DbSession):
    auth_service = AuthService(session)
    return await auth_service.refresh(data.refresh_token)
