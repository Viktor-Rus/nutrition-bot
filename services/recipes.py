from aiogram import types
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from recipes import RECIPE_CATEGORIES, RECIPES


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
    ingredients = "\n".join([f"- {item}" for item in recipe["ingredients"]])
    steps = "\n".join([
        f"{index}. {step}"
        for index, step in enumerate(recipe["steps"], start=1)
    ])
    tags = ", ".join(recipe["tags"])
    parts = [
        f"{recipe['title']}\n\n"
        f"Время: {recipe['time']}\n"
        f"Раздел: {get_category_title(recipe['category'])}"
    ]

    if recipe.get("servings"):
        parts.append(f"Порции: {recipe['servings']}")

    parts.append(f"Теги: {tags}")

    if recipe.get("summary"):
        parts.append(f"Коротко:\n{recipe['summary']}")

    parts.append(f"Ингредиенты:\n{ingredients}")

    if recipe.get("serving"):
        serving = "\n".join([f"- {item}" for item in recipe["serving"]])
        parts.append(f"Для подачи:\n{serving}")

    parts.append(f"Как готовить:\n{steps}")

    if recipe.get("notes"):
        notes = "\n".join([f"- {item}" for item in recipe["notes"]])
        parts.append(f"Важные нюансы:\n{notes}")

    if recipe.get("habit_tip"):
        parts.append(f"Маленький лайфхак:\n{recipe['habit_tip']}")

    return "\n\n".join(parts)


async def send_recipe_detail(message: types.Message, recipe_id: str, recipe):
    image_path = recipe.get("image_path")

    if image_path:
        await message.answer_photo(
            photo=FSInputFile(image_path),
        )

    await message.answer(
        format_recipe(recipe),
        reply_markup=recipe_detail_keyboard(recipe_id)
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
