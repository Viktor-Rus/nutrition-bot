from aiogram import Dispatcher, types
from aiogram.filters import Command

from keyboards import MENU_HELP, help_text, main_keyboard
from services.users import maybe_upsert_private_user
from state import PENDING_ACTIONS


def register(dp: Dispatcher):
    @dp.message(Command("start"))
    async def start(message: types.Message):
        maybe_upsert_private_user(message)

        await message.answer(
            "👋 Добро пожаловать в MealAdvisor!\n\n"
            "Я — AI-нутрициолог, который помогает разбираться в питании "
            "и делать более осознанный выбор.\n\n"
            f"{help_text()}",
            reply_markup=main_keyboard()
        )

    @dp.message(Command("help"))
    async def help_command(message: types.Message):
        maybe_upsert_private_user(message)
        await message.answer(help_text(), reply_markup=main_keyboard())

    @dp.message(lambda message: message.text == MENU_HELP)
    async def menu_help(message: types.Message):
        maybe_upsert_private_user(message)
        PENDING_ACTIONS.pop(message.from_user.id, None)
        await message.answer(help_text(), reply_markup=main_keyboard())
