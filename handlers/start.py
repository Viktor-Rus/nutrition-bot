from aiogram import Dispatcher, types
from aiogram.filters import Command

from keyboards import MENU_HELP, help_text, main_keyboard
from services.payments import (
    PAYMENT_CALLBACK,
    answer_pre_checkout_query,
    handle_successful_payment,
    send_payment_invoice,
    start_offer_keyboard,
    start_offer_text,
)
from services.users import maybe_upsert_private_user
from state import PENDING_ACTIONS


def register(dp: Dispatcher):
    @dp.message(Command("start"))
    async def start(message: types.Message):
        maybe_upsert_private_user(message)

        await message.answer(
            start_offer_text(),
            reply_markup=start_offer_keyboard()
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

    @dp.callback_query(lambda callback: callback.data == PAYMENT_CALLBACK)
    async def payment_callback(callback: types.CallbackQuery):
        await callback.answer()
        await send_payment_invoice(callback.message)

    @dp.pre_checkout_query()
    async def pre_checkout_query_handler(pre_checkout_query: types.PreCheckoutQuery):
        await answer_pre_checkout_query(pre_checkout_query)

    @dp.message(lambda message: message.successful_payment)
    async def successful_payment_handler(message: types.Message):
        maybe_upsert_private_user(message)
        await handle_successful_payment(message)
