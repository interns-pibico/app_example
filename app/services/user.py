from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> User:
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        result = await self.session.execute(select(User).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create(self, data: UserCreate) -> User:
        if await self.get_by_email(data.email):
            raise ConflictError("Email already registered")
        if await self.get_by_username(data.username):
            raise ConflictError("Username already taken")

        user = User(
            email=data.email,
            username=data.username,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update(self, user_id: int, data: UserUpdate) -> User:
        user = await self.get_by_id(user_id)
        update_data = data.model_dump(exclude_unset=True)

        if "password" in update_data:
            update_data["hashed_password"] = hash_password(update_data.pop("password"))

        for field, value in update_data.items():
            setattr(user, field, value)

        await self.session.flush()
        return user

    async def delete(self, user_id: int) -> None:
        user = await self.get_by_id(user_id)
        await self.session.delete(user)
        await self.session.flush()
