from aiogram import Dispatcher, types
from aiogram.filters import Command

from keyboards import main_keyboard
from services.payments import (
    SUBSCRIPTION_CANCEL_CALLBACK,
    SUBSCRIPTION_CANCEL_CONFIRM_CALLBACK,
    SUBSCRIPTION_CANCEL_KEEP_CALLBACK,
    SUBSCRIPTION_START_CALLBACK,
    SUBSCRIPTION_STATUS_CALLBACK,
    cancel_user_subscription,
    request_subscription_cancel_confirmation,
    send_subscription_status,
    start_subscription,
)
from services.users import maybe_upsert_private_user


async def clear_inline_keyboard(callback: types.CallbackQuery):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        print("SUBSCRIPTION CLEAR MARKUP ERROR:", repr(e))


def register(dp: Dispatcher):
    @dp.message(Command("subscription"))
    async def subscription_command(message: types.Message):
        maybe_upsert_private_user(message)
        await send_subscription_status(message, message.from_user.id)

    @dp.message(Command("cancel_subscription"))
    async def cancel_subscription_command(message: types.Message):
        maybe_upsert_private_user(message)
        await request_subscription_cancel_confirmation(message, message.from_user.id)

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
        await clear_inline_keyboard(callback)
        await request_subscription_cancel_confirmation(callback.message, callback.from_user.id)

    @dp.callback_query(lambda callback: callback.data == SUBSCRIPTION_CANCEL_CONFIRM_CALLBACK)
    async def subscription_cancel_confirm_callback(callback: types.CallbackQuery):
        await callback.answer()
        await clear_inline_keyboard(callback)
        await cancel_user_subscription(callback.message, callback.from_user.id)

    @dp.callback_query(lambda callback: callback.data == SUBSCRIPTION_CANCEL_KEEP_CALLBACK)
    async def subscription_cancel_keep_callback(callback: types.CallbackQuery):
        await callback.answer("Подписка сохранена")
        await clear_inline_keyboard(callback)
        await callback.message.answer(
            "Хорошо, подписку оставили активной.",
            reply_markup=main_keyboard()
        )
