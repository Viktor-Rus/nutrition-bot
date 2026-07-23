from aiogram import Dispatcher, types

from keyboards import MENU_CANCEL, main_keyboard
from services.access import require_recipes_subscription
from services.memory import delete_memory_from_text, save_memory_from_text
from services.payments import (
    SUBSCRIPTION_CHANGE_CARD_RECEIPT_EMAIL_ACTION,
    SUBSCRIPTION_RECEIPT_EMAIL_ACTION,
    process_subscription_receipt_email,
)
from services.profile import PROFILE_TEXT_ACTIONS, handle_profile_pending_message
from services.recipes import recipe_search_results_keyboard, search_recipes, send_recipe_book
from services.support import send_feedback_to_support
from services.users import maybe_upsert_private_user
from state import (
    PENDING_ACTIONS,
    PROFILE_DRAFTS,
    mark_pending_message_consumed,
)


def register(dp: Dispatcher):
    @dp.message(lambda message: message.text == MENU_CANCEL)
    async def menu_cancel(message: types.Message):
        maybe_upsert_private_user(message)
        mark_pending_message_consumed(message)
        PENDING_ACTIONS.pop(message.from_user.id, None)
        PROFILE_DRAFTS.pop(message.from_user.id, None)
        await message.answer("Ок, отменил действие.", reply_markup=main_keyboard())

    @dp.message(lambda message: PENDING_ACTIONS.get(message.from_user.id) == "feedback")
    async def handle_feedback_message(message: types.Message):
        maybe_upsert_private_user(message)
        mark_pending_message_consumed(message)
        PENDING_ACTIONS.pop(message.from_user.id, None)
        await send_feedback_to_support(message)

    @dp.message(lambda message: message.text and message.from_user.id in PENDING_ACTIONS)
    async def handle_pending_action(message: types.Message):
        maybe_upsert_private_user(message)
        mark_pending_message_consumed(message)
        action = PENDING_ACTIONS.get(message.from_user.id)
        text = message.text.strip()

        if action in PROFILE_TEXT_ACTIONS:
            await handle_profile_pending_message(message, action, text)
            return

        action = PENDING_ACTIONS.pop(message.from_user.id)

        if action == "remember":
            await save_memory_from_text(message, text)
            return

        if action == "forget":
            await delete_memory_from_text(message, text)
            return

        if action in (
            SUBSCRIPTION_RECEIPT_EMAIL_ACTION,
            SUBSCRIPTION_CHANGE_CARD_RECEIPT_EMAIL_ACTION,
        ):
            await process_subscription_receipt_email(message, text, action)
            return

        if action == "recipe_search":
            if not await require_recipes_subscription(message, message.from_user.id):
                return

            results = search_recipes(text)

            if not results:
                await message.answer(
                    "Не нашёл рецепты по такому запросу. Попробуй другое слово или открой разделы.",
                    reply_markup=main_keyboard()
                )
                await send_recipe_book(message)
                return

            await message.answer(
                f"Нашёл рецепты по запросу «{text}»:",
                reply_markup=recipe_search_results_keyboard(results)
            )
            return

        await message.answer("Не понял действие. Попробуй ещё раз.", reply_markup=main_keyboard())
