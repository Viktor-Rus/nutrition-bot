from aiogram import Dispatcher, types

from keyboards import MENU_CANCEL, main_keyboard
from services.memory import delete_memory_from_text, save_memory_from_text
from services.recipes import recipe_search_results_keyboard, search_recipes, send_recipe_book
from services.support import send_feedback_to_support
from services.users import maybe_upsert_private_user
from state import PENDING_ACTIONS


def register(dp: Dispatcher):
    @dp.message(lambda message: message.text == MENU_CANCEL)
    async def menu_cancel(message: types.Message):
        maybe_upsert_private_user(message)
        PENDING_ACTIONS.pop(message.from_user.id, None)
        await message.answer("Ок, отменил действие.", reply_markup=main_keyboard())

    @dp.message(lambda message: message.text and message.from_user.id in PENDING_ACTIONS)
    async def handle_pending_action(message: types.Message):
        maybe_upsert_private_user(message)
        action = PENDING_ACTIONS.pop(message.from_user.id)
        text = message.text.strip()

        if action == "remember":
            await save_memory_from_text(message, text)
            return

        if action == "forget":
            await delete_memory_from_text(message, text)
            return

        if action == "recipe_search":
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

        if action == "feedback":
            await send_feedback_to_support(message, text)
            return

        await message.answer("Не понял действие. Попробуй ещё раз.", reply_markup=main_keyboard())
