from aiogram import Dispatcher, types
from aiogram.filters import Command

from keyboards import MENU_HELP, help_actions_keyboard, help_text
from services.payments import (
    activate_free_trial,
    get_subscription,
    has_used_trial,
    start_offer_keyboard,
    start_offer_text,
)
from services.users import maybe_upsert_private_user
from state import PENDING_ACTIONS


def register(dp: Dispatcher):
    @dp.message(Command("start"))
    async def start(message: types.Message):
        maybe_upsert_private_user(message)
        subscription = get_subscription(message.from_user.id)

        if not has_used_trial(subscription):
            activate_free_trial(message.from_user.id)
            subscription = get_subscription(message.from_user.id)

        await message.answer(
            start_offer_text(subscription),
            reply_markup=start_offer_keyboard(subscription)
        )

    @dp.message(Command("help"))
    async def help_command(message: types.Message):
        maybe_upsert_private_user(message)
        await message.answer(
            help_text(),
            reply_markup=help_actions_keyboard()
        )

    @dp.message(lambda message: message.text == MENU_HELP)
    async def menu_help(message: types.Message):
        maybe_upsert_private_user(message)
        PENDING_ACTIONS.pop(message.from_user.id, None)
        await message.answer(
            help_text(),
            reply_markup=help_actions_keyboard()
        )
