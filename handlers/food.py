from aiogram import Dispatcher, types

from services.access import (
    require_food_analysis_subscription,
    require_subscription_callback,
)
from services.food_analysis import (
    FOOD_ACTION_IMPROVE_TOMORROW,
    FOOD_ACTION_REPLACEMENT,
    FOOD_ACTION_SAVE_HABIT,
    analyze_food_photo,
    analyze_food_text,
    answer_food_action,
)
from services.profile import maybe_update_profile_from_text
from services.users import maybe_upsert_private_user, upsert_user_profile
from state import PENDING_ACTIONS


def register(dp: Dispatcher):
    @dp.callback_query(
        lambda callback: callback.data in {
            FOOD_ACTION_IMPROVE_TOMORROW,
            FOOD_ACTION_REPLACEMENT,
            FOOD_ACTION_SAVE_HABIT,
        }
    )
    async def food_action_callback(callback: types.CallbackQuery):
        upsert_user_profile(callback.from_user)
        if not await require_subscription_callback(callback, "Продолжение анализа еды"):
            return
        await answer_food_action(callback, callback.data)

    @dp.message(lambda message: message.photo and message.from_user.id not in PENDING_ACTIONS)
    async def photo_handler(message: types.Message):
        maybe_upsert_private_user(message)
        if not await require_food_analysis_subscription(message, message.from_user.id):
            return
        await analyze_food_photo(message)

    @dp.message(lambda message: message.from_user.id not in PENDING_ACTIONS)
    async def analyze_food(message: types.Message):
        maybe_upsert_private_user(message)
        if message.text and await maybe_update_profile_from_text(message):
            return

        if not await require_food_analysis_subscription(message, message.from_user.id):
            return
        await analyze_food_text(message)
