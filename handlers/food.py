from aiogram import Dispatcher, types

from services.access import require_food_analysis_subscription
from services.food_analysis import analyze_food_photo, analyze_food_text
from services.users import maybe_upsert_private_user


def register(dp: Dispatcher):
    @dp.message(lambda message: message.photo)
    async def photo_handler(message: types.Message):
        maybe_upsert_private_user(message)
        if not await require_food_analysis_subscription(message, message.from_user.id):
            return
        await analyze_food_photo(message)

    @dp.message()
    async def analyze_food(message: types.Message):
        maybe_upsert_private_user(message)
        if not await require_food_analysis_subscription(message, message.from_user.id):
            return
        await analyze_food_text(message)
