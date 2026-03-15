from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate
from app.services.auth import get_current_user
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/", response_model=list[UserRead])
async def list_users(session: DbSession, current_user: CurrentUser, skip: int = 0, limit: int = 100):
    service = UserService(session)
    return await service.list_users(skip=skip, limit=limit)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUser):
    return current_user


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, session: DbSession, current_user: CurrentUser):
    service = UserService(session)
    return await service.get_by_id(user_id)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(user_id: int, data: UserUpdate, session: DbSession, current_user: CurrentUser):
    service = UserService(session)
    return await service.update(user_id, data)


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: int, session: DbSession, current_user: CurrentUser):
    service = UserService(session)
    await service.delete(user_id)
