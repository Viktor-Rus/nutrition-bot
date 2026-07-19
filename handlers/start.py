from aiogram import Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards import MENU_HELP, help_actions_keyboard, help_text
from services.payments import (
    activate_free_trial,
    get_subscription,
    has_used_trial,
    start_offer_keyboard,
    start_offer_text,
)
from services.profile import PROFILE_START_CALLBACK
from services.users import maybe_upsert_private_user
from state import PENDING_ACTIONS


START_ACTION_PHOTO_CALLBACK = "start_action:photo"
START_ACTION_COMPOSITION_CALLBACK = "start_action:composition"
START_ACTION_DINNER_CALLBACK = "start_action:dinner"


def start_onboarding_keyboard(subscription=None):
    subscription_keyboard = start_offer_keyboard(subscription)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📸 Разобрать фото еды",
                    callback_data=START_ACTION_PHOTO_CALLBACK,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🧾 Проверить состав",
                    callback_data=START_ACTION_COMPOSITION_CALLBACK,
                ),
                InlineKeyboardButton(
                    text="🍽 Подобрать ужин",
                    callback_data=START_ACTION_DINNER_CALLBACK,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Настроить под себя",
                    callback_data=PROFILE_START_CALLBACK,
                ),
            ],
            *subscription_keyboard.inline_keyboard,
        ]
    )


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
            reply_markup=start_onboarding_keyboard(subscription)
        )

    @dp.callback_query(lambda callback: callback.data == START_ACTION_PHOTO_CALLBACK)
    async def start_action_photo(callback: types.CallbackQuery):
        await callback.answer()
        await callback.message.answer(
            "Пришли фото еды, перекуса или напитка 📸\n\n"
            "Можно обычное фото без красивой подачи. Я мягко подскажу, "
            "что уже нормально и что можно чуть улучшить."
        )

    @dp.callback_query(lambda callback: callback.data == START_ACTION_COMPOSITION_CALLBACK)
    async def start_action_composition(callback: types.CallbackQuery):
        await callback.answer()
        await callback.message.answer(
            "Пришли фото состава продукта или упаковки 🧾\n\n"
            "Я переведу сложные ингредиенты на понятный язык и подскажу, "
            "стоит ли брать этот продукт."
        )

    @dp.callback_query(lambda callback: callback.data == START_ACTION_DINNER_CALLBACK)
    async def start_action_dinner(callback: types.CallbackQuery):
        await callback.answer()
        await callback.message.answer(
            "Напиши, что есть дома и сколько времени на готовку 🍽\n\n"
            "Например: «есть курица, яйца и овощи, нужно за 20 минут». "
            "Я предложу простой вариант ужина."
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
