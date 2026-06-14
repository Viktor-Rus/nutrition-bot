from aiogram import types
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from html import escape

from recipes import RECIPE_CATEGORIES, RECIPES


RECIPE_IMAGE_FILE_IDS = {}


def get_category_title(category_id: str):
    for current_id, title in RECIPE_CATEGORIES:
        if current_id == category_id:
            return title
    return "Рецепты"


def recipe_categories_keyboard():
    rows = []

    for index in range(0, len(RECIPE_CATEGORIES), 2):
        row = []
        for category_id, title in RECIPE_CATEGORIES[index:index + 2]:
            row.append(
                InlineKeyboardButton(
                    text=title,
                    callback_data=f"recipes:cat:{category_id}"
                )
            )
        rows.append(row)

    rows.append([
        InlineKeyboardButton(text="Поиск рецепта", callback_data="recipes:search")
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def recipes_by_category(category_id: str):
    return [
        (recipe_id, recipe)
        for recipe_id, recipe in RECIPES.items()
        if recipe["category"] == category_id
    ]


def recipe_list_keyboard(category_id: str):
    rows = [
        [
            InlineKeyboardButton(
                text=recipe["title"],
                callback_data=f"recipes:view:{recipe_id}"
            )
        ]
        for recipe_id, recipe in recipes_by_category(category_id)
    ]

    rows.append([
        InlineKeyboardButton(text="Назад к разделам", callback_data="recipes:home"),
        InlineKeyboardButton(text="Поиск", callback_data="recipes:search"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def recipe_detail_keyboard(recipe_id: str):
    category_id = RECIPES[recipe_id]["category"]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Назад к разделу",
                    callback_data=f"recipes:cat:{category_id}"
                )
            ],
            [
                InlineKeyboardButton(text="Все разделы", callback_data="recipes:home"),
                InlineKeyboardButton(text="Поиск", callback_data="recipes:search"),
            ],
        ]
    )


def recipe_search_results_keyboard(results):
    rows = [
        [
            InlineKeyboardButton(
                text=recipe["title"],
                callback_data=f"recipes:view:{recipe_id}"
            )
        ]
        for recipe_id, recipe in results
    ]

    rows.append([
        InlineKeyboardButton(text="Все разделы", callback_data="recipes:home"),
        InlineKeyboardButton(text="Новый поиск", callback_data="recipes:search"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_recipe(recipe):
    ingredients = "\n".join([f"• {escape(item)}" for item in recipe["ingredients"]])
    steps = "\n".join([
        f"<b>{index}.</b> {escape(step)}"
        for index, step in enumerate(recipe["steps"], start=1)
    ])
    tags = ", ".join([f"#{escape(tag.replace(' ', '_'))}" for tag in recipe["tags"]])
    parts = [
        f"🥕🥥 <b>{escape(recipe['title'])}</b>",
        (
            f"⏱ <b>Время:</b> {escape(recipe['time'])}\n"
            f"📂 <b>Раздел:</b> {escape(get_category_title(recipe['category']))}"
        ),
    ]

    if recipe.get("servings"):
        parts.append(f"🍽 <b>Порции:</b> {escape(recipe['servings'])}")

    parts.append(f"🏷 <b>Теги:</b> {tags}")

    if recipe.get("summary"):
        parts.append(f"✨ <b>Коротко</b>\n{escape(recipe['summary'])}")

    parts.append(f"🛒 <b>Ингредиенты</b>\n{ingredients}")

    if recipe.get("serving"):
        serving = "\n".join([f"• {escape(item)}" for item in recipe["serving"]])
        parts.append(f"🌿 <b>Для подачи</b>\n{serving}")

    parts.append(f"👩‍🍳 <b>Как готовить</b>\n{steps}")

    if recipe.get("notes"):
        notes = "\n".join([f"• {escape(item)}" for item in recipe["notes"]])
        parts.append(f"☝️ <b>Важные нюансы</b>\n{notes}")

    if recipe.get("habit_tip"):
        parts.append(f"👣 <b>Маленький лайфхак</b>\n{escape(recipe['habit_tip'])}")

    return "\n\n".join(parts)


async def send_recipe_detail(message: types.Message, recipe_id: str, recipe):
    image_path = recipe.get("image_path")

    if image_path:
        cached_file_id = RECIPE_IMAGE_FILE_IDS.get(recipe_id)
        photo = cached_file_id or FSInputFile(image_path)
        photo_message = await message.answer_photo(photo=photo)

        if not cached_file_id and photo_message.photo:
            RECIPE_IMAGE_FILE_IDS[recipe_id] = photo_message.photo[-1].file_id

    await message.answer(
        format_recipe(recipe),
        reply_markup=recipe_detail_keyboard(recipe_id),
        parse_mode="HTML",
    )


def search_recipes(query: str, limit: int = 10):
    normalized_query = (query or "").lower().replace("ё", "е").strip()

    if not normalized_query:
        return []

    results = []

    for recipe_id, recipe in RECIPES.items():
        searchable_text = " ".join([
            recipe["title"],
            get_category_title(recipe["category"]),
            " ".join(recipe["ingredients"]),
            " ".join(recipe["tags"]),
            recipe.get("summary", ""),
            " ".join(recipe.get("serving", [])),
            " ".join(recipe.get("notes", [])),
            recipe.get("habit_tip", ""),
        ]).lower().replace("ё", "е")

        if normalized_query in searchable_text:
            results.append((recipe_id, recipe))

    return results[:limit]


async def send_recipe_book(message: types.Message):
    await message.answer(
        "Книга рецептов\n\nВыбери раздел или воспользуйся поиском.",
        reply_markup=recipe_categories_keyboard()
    )
