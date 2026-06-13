from aiogram import Dispatcher, types
from aiogram.filters import Command

from services.payments import (
    SUBSCRIPTION_CANCEL_CALLBACK,
    SUBSCRIPTION_START_CALLBACK,
    SUBSCRIPTION_STATUS_CALLBACK,
    cancel_user_subscription,
    send_subscription_status,
    start_subscription,
)
from services.users import maybe_upsert_private_user


def register(dp: Dispatcher):
    @dp.message(Command("subscription"))
    async def subscription_command(message: types.Message):
        maybe_upsert_private_user(message)
        await send_subscription_status(message, message.from_user.id)

    @dp.message(Command("cancel_subscription"))
    async def cancel_subscription_command(message: types.Message):
        maybe_upsert_private_user(message)
        await cancel_user_subscription(message, message.from_user.id)

    @dp.callback_query(lambda callback: callback.data == SUBSCRIPTION_START_CALLBACK)
    async def subscription_start_callback(callback: types.CallbackQuery):
        await callback.answer()
        await start_subscription(callback.message, callback.from_user.id)

    @dp.callback_query(lambda callback: callback.data == SUBSCRIPTION_STATUS_CALLBACK)
    async def subscription_status_callback(callback: types.CallbackQuery):
        await callback.answer()
        await send_subscription_status(callback.message, callback.from_user.id)

    @dp.callback_query(lambda callback: callback.data == SUBSCRIPTION_CANCEL_CALLBACK)
    async def subscription_cancel_callback(callback: types.CallbackQuery):
        await callback.answer()
        await cancel_user_subscription(callback.message, callback.from_user.id)
