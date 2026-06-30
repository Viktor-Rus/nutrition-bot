from aiogram import Dispatcher, types
from aiogram.filters import Command

from keyboards import MENU_FEEDBACK, cancel_keyboard
from services.users import maybe_upsert_private_user, upsert_user_profile
from state import PENDING_ACTIONS


def register(dp: Dispatcher):
    async def request_feedback(message: types.Message, user_id: int):
        PENDING_ACTIONS[user_id] = "feedback"
        await message.answer(
            "Напиши сообщение для разработчика. Я передам его в поддержку.",
            reply_markup=cancel_keyboard()
        )

    @dp.message(Command("feedback"))
    async def feedback_command(message: types.Message):
        maybe_upsert_private_user(message)
        await request_feedback(message, message.from_user.id)

    @dp.message(lambda message: message.text == MENU_FEEDBACK)
    async def menu_feedback(message: types.Message):
        maybe_upsert_private_user(message)
        await request_feedback(message, message.from_user.id)

    @dp.callback_query(lambda callback: callback.data == "feedback:start")
    async def feedback_start_callback(callback: types.CallbackQuery):
        upsert_user_profile(callback.from_user)
        await callback.answer()
        await request_feedback(callback.message, callback.from_user.id)
