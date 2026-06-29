from aiogram import Dispatcher, types
from aiogram.filters import Command

from keyboards import MENU_RECIPES, main_keyboard
from recipes import RECIPES
from services.access import (
    require_recipes_subscription,
    require_recipes_subscription_callback,
)
from services.recipes import (
    get_category_title,
    recipe_categories_keyboard,
    recipe_list_keyboard,
    recipes_by_category,
    send_recipe_detail,
    send_recipe_book,
    send_recipe_full,
)
from services.users import maybe_upsert_private_user
from state import PENDING_ACTIONS


async def show_recipe_navigation(callback: types.CallbackQuery, text: str, reply_markup):
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=reply_markup,
        )
        return

    await callback.message.edit_text(text, reply_markup=reply_markup)


def register(dp: Dispatcher):
    @dp.message(Command("recipes"))
    async def recipes_command(message: types.Message):
        maybe_upsert_private_user(message)
        PENDING_ACTIONS.pop(message.from_user.id, None)
        if not await require_recipes_subscription(message, message.from_user.id):
            return
        await send_recipe_book(message)

    @dp.message(lambda message: message.text == MENU_RECIPES)
    async def menu_recipes(message: types.Message):
        maybe_upsert_private_user(message)
        PENDING_ACTIONS.pop(message.from_user.id, None)
        if not await require_recipes_subscription(message, message.from_user.id):
            return
        await send_recipe_book(message)

    @dp.callback_query(lambda callback: callback.data == "recipes:home")
    async def recipes_home_callback(callback: types.CallbackQuery):
        if not await require_recipes_subscription_callback(callback):
            return

        await callback.answer()
        await show_recipe_navigation(
            callback,
            "Книга рецептов\n\nВыбери раздел или воспользуйся поиском.",
            recipe_categories_keyboard()
        )

    @dp.callback_query(lambda callback: callback.data == "recipes:search")
    async def recipes_search_callback(callback: types.CallbackQuery):
        if not await require_recipes_subscription_callback(callback):
            return

        PENDING_ACTIONS[callback.from_user.id] = "recipe_search"
        await callback.answer()
        await callback.message.answer(
            "Что ищем? Напиши название, ингредиент или тег.\n\n"
            "Например: креветки, завтрак, суп, тофу",
            reply_markup=main_keyboard()
        )

    @dp.callback_query(lambda callback: (callback.data or "").startswith("recipes:cat:"))
    async def recipes_category_callback(callback: types.CallbackQuery):
        if not await require_recipes_subscription_callback(callback):
            return

        category_id = callback.data.split(":", maxsplit=2)[2]
        title = get_category_title(category_id)
        category_recipes = recipes_by_category(category_id)

        await callback.answer()

        if not category_recipes:
            await show_recipe_navigation(
                callback,
                f"{title}\n\nВ этом разделе пока нет рецептов.",
                recipe_categories_keyboard()
            )
            return

        await show_recipe_navigation(
            callback,
            f"{title}\n\nВыбери рецепт:",
            recipe_list_keyboard(category_id)
        )

    @dp.callback_query(lambda callback: (callback.data or "").startswith("recipes:view:"))
    async def recipes_view_callback(callback: types.CallbackQuery):
        if not await require_recipes_subscription_callback(callback):
            return

        recipe_id = callback.data.split(":", maxsplit=2)[2]
        recipe = RECIPES.get(recipe_id)

        await callback.answer()

        if not recipe:
            await callback.message.edit_text(
                "Не нашёл этот рецепт. Вернись к разделам и выбери другой.",
                reply_markup=recipe_categories_keyboard()
            )
            return

        await send_recipe_detail(callback.message, recipe_id, recipe)

    @dp.callback_query(lambda callback: (callback.data or "").startswith("recipes:full:"))
    async def recipes_full_callback(callback: types.CallbackQuery):
        if not await require_recipes_subscription_callback(callback):
            return

        recipe_id = callback.data.split(":", maxsplit=2)[2]
        recipe = RECIPES.get(recipe_id)

        await callback.answer()

        if not recipe:
            await callback.message.answer(
                "Не нашёл этот рецепт. Вернись к разделам и выбери другой.",
                reply_markup=recipe_categories_keyboard()
            )
            return

        await send_recipe_full(callback.message, recipe_id, recipe)
