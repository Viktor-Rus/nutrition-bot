from aiogram import Dispatcher, types
from aiogram.filters import Command

from keyboards import MENU_FEEDBACK, cancel_keyboard
from services.users import maybe_upsert_private_user
from state import PENDING_ACTIONS


def register(dp: Dispatcher):
    @dp.message(Command("feedback"))
    async def feedback_command(message: types.Message):
        maybe_upsert_private_user(message)
        PENDING_ACTIONS[message.from_user.id] = "feedback"
        await message.answer(
            "Напиши сообщение для разработчика. Я передам его в поддержку.",
            reply_markup=cancel_keyboard()
        )

    @dp.message(lambda message: message.text == MENU_FEEDBACK)
    async def menu_feedback(message: types.Message):
        maybe_upsert_private_user(message)
        PENDING_ACTIONS[message.from_user.id] = "feedback"
        await message.answer(
            "Напиши сообщение для разработчика. Я передам его в поддержку.",
            reply_markup=cancel_keyboard()
        )
