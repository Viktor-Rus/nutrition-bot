from aiogram import types
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from html import escape

from recipes import RECIPE_CATEGORIES, RECIPES


RECIPE_IMAGE_FILE_IDS = {}
RECIPE_EMOJI_KEYWORDS = [
    ("🥤", ("коктейл", "эликсир", "напит", "смузи")),
    ("🍫", ("шоколад", "какао", "брауни")),
    ("🍞", ("хлеб", "лепеш", "тортиль")),
    ("🥚", ("яйц", "омлет", "пашот")),
    ("🥗", ("салат", "табуле")),
    ("🍲", ("суп", "бульон", "лазан", "ризотто")),
    ("🐟", ("рыб", "хек", "треск", "горбуш", "скумбр", "лосос")),
    ("🦐", ("кревет",)),
    ("🦑", ("кальмар",)),
    ("🦀", ("краб",)),
    ("🍗", ("кур", "индей", "птиц")),
    ("🥩", ("говяд", "телят", "мяс", "фарш", "печен", "сердеч", "язык", "субпродукт")),
    ("🥒", ("огур", "цуккини", "кабач")),
    ("🥬", ("капуст", "мангольд", "ботв", "шпинат", "руккол", "зелень")),
    ("🥕", ("морков",)),
    ("🧄", ("чеснок",)),
    ("🍅", ("томат", "помидор")),
    ("🥑", ("авокад",)),
    ("🍎", ("яблок",)),
    ("🍌", ("банан",)),
    ("🍋", ("лимон", "лайм")),
    ("🥥", ("кокос",)),
    ("🎃", ("тыкв",)),
    ("🥦", ("броккол", "брюссель")),
    ("🌾", ("греч", "киноа", "пшен", "рис", "чечев", "нут", "маш", "зерн")),
    ("🥜", ("орех", "миндал", "чиа", "лен", "семен")),
    ("🫜", ("свекл", "редьк")),
]
RECIPE_EMOJI_FALLBACKS = {
    "soups_broths": ["🍲"],
    "poultry": ["🍗"],
    "meat_offal": ["🥩"],
    "fish_seafood": ["🐟"],
    "eggs": ["🥚"],
    "vegetables_sides": ["🥗"],
    "grains_seeds": ["🌾"],
    "preserves": ["🫙"],
    "bakery_desserts": ["🍰"],
    "drinks": ["🥤"],
    "lifehacks": ["💡"],
}


def normalize_recipe_text(value: str):
    return (value or "").lower().replace("ё", "е").strip()


def get_recipe_title_emojis(recipe, max_count: int = 2):
    emojis = []
    sources = [
        recipe.get("title", ""),
        *recipe.get("ingredients", []),
        *recipe.get("tags", []),
        recipe.get("summary", ""),
    ]

    for source in sources:
        text = normalize_recipe_text(source)

        for emoji, keywords in RECIPE_EMOJI_KEYWORDS:
            if emoji in emojis:
                continue

            if any(keyword in text for keyword in keywords):
                emojis.append(emoji)

                if len(emojis) >= max_count:
                    return " ".join(emojis)

    for fallback_emoji in RECIPE_EMOJI_FALLBACKS.get(recipe.get("category"), []):
        if fallback_emoji not in emojis:
            emojis.append(fallback_emoji)
        if len(emojis) >= max_count:
            break

    if not emojis:
        return "🍽"

    return " ".join(emojis[:max_count])


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


def recipe_preview_keyboard(recipe_id: str):
    category_id = RECIPES[recipe_id]["category"]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Показать полный рецепт",
                    callback_data=f"recipes:full:{recipe_id}"
                )
            ],
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
    title_emojis = get_recipe_title_emojis(recipe)
    parts = [
        f"{title_emojis} <b>{escape(recipe['title'])}</b>",
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


def format_recipe_preview(recipe):
    title_emojis = get_recipe_title_emojis(recipe)
    parts = [
        f"{title_emojis} <b>{escape(recipe['title'])}</b>",
        (
            f"⏱ <b>Время:</b> {escape(recipe['time'])}\n"
            f"📂 <b>Раздел:</b> {escape(get_category_title(recipe['category']))}"
        ),
    ]

    if recipe.get("servings"):
        parts.append(f"🍽 <b>Порции:</b> {escape(recipe['servings'])}")

    if recipe.get("summary"):
        parts.append(f"✨ <b>Коротко</b>\n{escape(recipe['summary'])}")

    ingredients = "\n".join([
        f"• {escape(item)}"
        for item in recipe["ingredients"][:5]
    ])
    ingredients_suffix = "\n• ..." if len(recipe["ingredients"]) > 5 else ""
    parts.append(f"🛒 <b>Основные ингредиенты</b>\n{ingredients}{ingredients_suffix}")

    return "\n\n".join(parts)


async def send_recipe_detail(message: types.Message, recipe_id: str, recipe):
    image_path = recipe.get("image_path")
    caption = format_recipe_preview(recipe)

    if image_path:
        cached_file_id = RECIPE_IMAGE_FILE_IDS.get(recipe_id)
        photo = cached_file_id or FSInputFile(image_path)
        photo_message = await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=recipe_preview_keyboard(recipe_id),
            parse_mode="HTML",
        )

        if not cached_file_id and photo_message.photo:
            RECIPE_IMAGE_FILE_IDS[recipe_id] = photo_message.photo[-1].file_id
        return

    await message.answer(
        caption,
        reply_markup=recipe_preview_keyboard(recipe_id),
        parse_mode="HTML",
    )


async def send_recipe_full(message: types.Message, recipe_id: str, recipe):
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
