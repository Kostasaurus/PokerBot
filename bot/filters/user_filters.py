from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from core.settings import settings
from managers.user_manager import UserManager


class IsRegistered(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id
        return await UserManager.check_registration(user_id=user_id)

class IsNotRegistered(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id
        return not await UserManager.check_registration(user_id=user_id)

class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        is_admin = event.from_user.id in settings.bot.ADMINS
        return is_admin
