from aiogram import Dispatcher, types
from aiogram.filters import Command

from services.profile import (
    PROFILE_GOAL_PREFIX,
    PROFILE_START_CALLBACK,
    handle_profile_goal_callback,
    request_profile_setup,
)
from services.users import maybe_upsert_private_user, upsert_user_profile


def register(dp: Dispatcher):
    @dp.message(Command("profile"))
    async def profile_command(message: types.Message):
        maybe_upsert_private_user(message)
        await request_profile_setup(message, message.from_user.id)

    @dp.callback_query(lambda callback: callback.data == PROFILE_START_CALLBACK)
    async def profile_start_callback(callback: types.CallbackQuery):
        upsert_user_profile(callback.from_user)
        await callback.answer()
        await request_profile_setup(callback.message, callback.from_user.id)

    @dp.callback_query(lambda callback: (callback.data or "").startswith(PROFILE_GOAL_PREFIX))
    async def profile_goal_callback(callback: types.CallbackQuery):
        upsert_user_profile(callback.from_user)
        await handle_profile_goal_callback(callback)
