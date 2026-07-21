import asyncio

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
    analyze_food_photo_album,
    analyze_food_text,
    answer_food_action,
)
from services.profile import maybe_update_profile_from_text
from services.users import maybe_upsert_private_user, upsert_user_profile
from state import PENDING_ACTIONS


MEDIA_GROUP_BUFFER = {}
MEDIA_GROUP_TASKS = {}
MEDIA_GROUP_DELAY_SECONDS = 1.2


async def process_media_group_after_delay(key):
    try:
        await asyncio.sleep(MEDIA_GROUP_DELAY_SECONDS)
    except asyncio.CancelledError:
        return

    messages = MEDIA_GROUP_BUFFER.pop(key, [])
    MEDIA_GROUP_TASKS.pop(key, None)

    if not messages:
        return

    messages = sorted(messages, key=lambda item: item.message_id)
    first_message = messages[0]

    maybe_upsert_private_user(first_message)
    if not await require_food_analysis_subscription(
        first_message,
        first_message.from_user.id
    ):
        return

    await analyze_food_photo_album(first_message, messages)


def enqueue_media_group(message: types.Message):
    key = (message.chat.id, message.media_group_id)
    MEDIA_GROUP_BUFFER.setdefault(key, []).append(message)

    previous_task = MEDIA_GROUP_TASKS.pop(key, None)
    if previous_task:
        previous_task.cancel()

    MEDIA_GROUP_TASKS[key] = asyncio.create_task(
        process_media_group_after_delay(key)
    )


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
        if message.media_group_id:
            enqueue_media_group(message)
            return

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
