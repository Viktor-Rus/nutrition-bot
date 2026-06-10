import os
import base64

from dotenv import load_dotenv
from fastapi import FastAPI, Request

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from openai import OpenAI
from recipes import RECIPE_CATEGORIES, RECIPES
from supabase import create_client

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_VECTOR_STORE_ID = os.getenv("OPENAI_VECTOR_STORE_ID")
SUPPORT_CHAT_ID = os.getenv("SUPPORT_CHAT_ID")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

openai_client = OpenAI(api_key=OPENAI_API_KEY)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

app = FastAPI()


BOT_COMMANDS = [
    BotCommand(command="start", description="Запустить бота"),
    BotCommand(command="help", description="Что умеет бот"),
    BotCommand(command="recipes", description="Открыть книгу рецептов"),
    BotCommand(command="feedback", description="Написать обратную связь"),
    BotCommand(command="memory", description="Показать сохранённые факты"),
    BotCommand(command="remember", description="Добавить факт в память"),
    BotCommand(command="forget", description="Удалить факт из памяти"),
]

MENU_RECIPES = "Книга рецептов"
MENU_MEMORY = "Память"
MENU_REMEMBER = "Добавить факт"
MENU_FORGET = "Удалить факт"
MENU_FEEDBACK = "Обратная связь"
MENU_HELP = "Помощь"
MENU_CANCEL = "Отмена"

PENDING_ACTIONS = {}

def load_bot_role():
    try:
        with open("prompt.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return """
Ты — личный AI-нутрициолог и консультант по здоровому образу жизни.

Отвечай по структуре:
1️⃣ Анализ
2️⃣ Что хорошо
3️⃣ Что можно улучшить
4️⃣ Практический совет
5️⃣ Вопрос пользователю

Не ставь медицинские диагнозы.
Если информации недостаточно — задай уточняющий вопрос.
"""


BOT_ROLE = load_bot_role()


def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=MENU_RECIPES),
                KeyboardButton(text=MENU_MEMORY),
            ],
            [
                KeyboardButton(text=MENU_REMEMBER),
                KeyboardButton(text=MENU_FORGET),
            ],
            [
                KeyboardButton(text=MENU_FEEDBACK),
                KeyboardButton(text=MENU_HELP),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Опиши еду или выбери действие",
    )


def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=MENU_CANCEL),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Отправь значение или нажми Отмена",
    )


def help_text():
    return (
        "Что я умею:\n\n"
        "📸 Анализировать еду по фото\n"
        "🥗 Анализировать блюда и продукты по описанию\n"
        "📦 Разбирать состав продуктов по фото упаковки\n"
        "🌍 Переводить составы с английского и других языков на русский\n"
        "📚 Показывать книгу рецептов по разделам\n"
        "💡 Давать персональные рекомендации по питанию и привычкам\n"
        "🧠 Запоминать важные факты через /remember\n"
        "🗑 Удалять факты из памяти через /forget\n\n"
        "✉️ Принимать обратную связь через кнопку «Обратная связь»\n\n"
        "Можно просто написать, что ты съел, или отправить фото еды."
    )


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

    return (
        f"{recipe['title']}\n\n"
        f"Время: {recipe['time']}\n"
        f"Раздел: {get_category_title(recipe['category'])}\n"
        f"Теги: {tags}\n\n"
        f"Ингредиенты:\n{ingredients}\n\n"
        f"Как готовить:\n{steps}"
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
        ]).lower().replace("ё", "е")

        if normalized_query in searchable_text:
            results.append((recipe_id, recipe))

    return results[:limit]


async def send_recipe_book(message: types.Message):
    await message.answer(
        "Книга рецептов\n\nВыбери раздел или воспользуйся поиском.",
        reply_markup=recipe_categories_keyboard()
    )


async def send_feedback_to_support(message: types.Message, feedback_text: str):
    if not SUPPORT_CHAT_ID:
        await message.answer(
            "Обратная связь временно недоступна. Попробуй позже.",
            reply_markup=main_keyboard()
        )
        return

    user = message.from_user
    username = f"@{user.username}" if user.username else "не указан"
    full_name = user.full_name or "не указано"

    support_message = (
        "Новое сообщение обратной связи\n\n"
        f"Пользователь: {full_name}\n"
        f"Username: {username}\n"
        f"Telegram ID: {user.id}\n\n"
        f"Сообщение:\n{feedback_text}"
    )

    try:
        await bot.send_message(chat_id=SUPPORT_CHAT_ID, text=support_message)
    except Exception as e:
        print("FEEDBACK SEND ERROR:", repr(e))
        await message.answer(
            "Не смог отправить сообщение. Попробуй ещё раз позже.",
            reply_markup=main_keyboard()
        )
        return

    await message.answer(
        "Спасибо! Я передал сообщение разработчику.",
        reply_markup=main_keyboard()
    )


def is_support_chat(chat_id: int):
    return SUPPORT_CHAT_ID and str(chat_id) == str(SUPPORT_CHAT_ID)


async def send_support_message(message: types.Message, command: str, prefix: str = ""):
    if not is_support_chat(message.chat.id):
        await message.answer("Эта команда доступна только в чате поддержки.")
        return

    parts = (message.text or "").split(maxsplit=2)

    if len(parts) < 3:
        await message.answer(
            "Формат:\n\n"
            f"/{command} TELEGRAM_ID текст сообщения\n\n"
            f"Например: /{command} 367204483 Спасибо за сообщение!"
        )
        return

    user_id_text = parts[1].strip()
    message_text = parts[2].strip()

    if not user_id_text.isdigit() or not message_text:
        await message.answer(
            "Не понял ID пользователя или текст сообщения.\n\n"
            f"Пример: /{command} 367204483 Спасибо за сообщение!"
        )
        return

    outgoing_text = f"{prefix}\n\n{message_text}" if prefix else message_text

    try:
        await bot.send_message(
            chat_id=int(user_id_text),
            text=outgoing_text
        )
    except Exception as e:
        print("SUPPORT MESSAGE SEND ERROR:", repr(e))
        await message.answer(
            "Не смог отправить сообщение пользователю. "
            "Проверь Telegram ID и что пользователь уже писал боту."
        )
        return

    await message.answer("Сообщение отправлено пользователю.")


async def send_support_reply(message: types.Message):
    await send_support_message(
        message=message,
        command="reply",
        prefix="Ответ поддержки:"
    )


async def send_support_direct_message(message: types.Message):
    await send_support_message(message=message, command="send")


@app.get("/")
async def root():
    return {"status": "bot is running"}


async def setup_bot_menu():
    await bot.set_my_commands(BOT_COMMANDS)


@app.on_event("startup")
async def on_startup():
    try:
        await setup_bot_menu()
    except Exception as e:
        print("BOT MENU SETUP ERROR:", repr(e))


def get_chat_history(telegram_id: int, limit: int = 10):
    result = (
        supabase.table("messages")
        .select("role, content")
        .eq("telegram_id", telegram_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    rows = result.data or []
    rows.reverse()

    return rows


def get_user_memory_facts(telegram_id: int, limit: int = 20):
    result = (
        supabase.table("user_memory")
        .select("fact")
        .eq("telegram_id", telegram_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return [
        item["fact"]
        for item in result.data or []
        if item.get("fact")
    ]


def get_user_memory(telegram_id: int):
    facts = get_user_memory_facts(telegram_id)

    if not facts:
        return ""

    return "\n".join([f"- {fact}" for fact in facts])


def build_user_memory_context(telegram_id: int):
    memory = get_user_memory(telegram_id)

    if not memory:
        memory = "Пока нет сохранённых фактов."

    return {
        "role": "system",
        "content": (
            "Долговременная память о пользователе:\n"
            f"{memory}\n\n"
            "Эти факты включают информацию, которую пользователь мог сохранить вручную через /remember. "
            "Обязательно учитывай их при анализе еды и персональных рекомендациях. "
            "Если сохранённый факт влияет на оценку блюда, ограничения, цели, аллергию, непереносимость, "
            "режим питания, сон, стресс или тренировки, адаптируй ответ под этот факт. "
            "Не советуй продукты и действия, которые конфликтуют с сохранёнными ограничениями пользователя. "
            "Не перечисляй всю память без необходимости, но кратко упоминай релевантный факт, "
            "если он объясняет рекомендацию. "
            "Не начинай ответ с фраз о том, что информация не найдена в загруженных файлах, документах "
            "или базе знаний. Если точных данных в материалах нет, просто дай полезный ответ из общих "
            "знаний и персонального контекста пользователя."
        )
    }


def save_user_memory_fact(telegram_id: int, fact: str):
    fact = (fact or "").strip()

    if not fact:
        return "empty"

    existing = (
        supabase.table("user_memory")
        .select("fact")
        .eq("telegram_id", telegram_id)
        .eq("fact", fact)
        .execute()
    )

    if existing.data:
        return "duplicate"

    supabase.table("user_memory").insert({
        "telegram_id": telegram_id,
        "fact": fact
    }).execute()

    return "saved"


def delete_user_memory_fact(telegram_id: int, fact: str):
    fact = (fact or "").strip()

    if not fact:
        return "empty"

    existing = (
        supabase.table("user_memory")
        .select("fact")
        .eq("telegram_id", telegram_id)
        .eq("fact", fact)
        .limit(1)
        .execute()
    )

    if not existing.data:
        return "not_found"

    supabase.table("user_memory").delete().eq(
        "telegram_id",
        telegram_id
    ).eq("fact", fact).execute()

    return "deleted"


async def save_memory_from_text(message: types.Message, fact: str):
    telegram_id = message.from_user.id

    try:
        status = save_user_memory_fact(telegram_id, fact)
    except Exception as e:
        print("MANUAL MEMORY SAVE ERROR:", repr(e))
        await message.answer(
            "Не смог сохранить факт в память. Попробуй ещё раз.",
            reply_markup=main_keyboard()
        )
        return

    if status == "duplicate":
        await message.answer("Этот факт уже есть в моей памяти.", reply_markup=main_keyboard())
        return

    await message.answer(
        "Запомнил. Посмотреть сохранённое можно через кнопку «Память» или /memory.",
        reply_markup=main_keyboard()
    )


async def delete_memory_from_text(message: types.Message, value: str):
    telegram_id = message.from_user.id
    value = (value or "").strip()

    try:
        if value.isdigit():
            facts = get_user_memory_facts(telegram_id)
            index = int(value)

            if index < 1 or index > len(facts):
                await message.answer(
                    "Не нашёл факт с таким номером. Проверь список через кнопку «Память».",
                    reply_markup=main_keyboard()
                )
                return

            fact = facts[index - 1]
        else:
            fact = value

        status = delete_user_memory_fact(telegram_id, fact)
    except Exception as e:
        print("MANUAL MEMORY DELETE ERROR:", repr(e))
        await message.answer(
            "Не смог удалить факт из памяти. Попробуй ещё раз.",
            reply_markup=main_keyboard()
        )
        return

    if status == "not_found":
        await message.answer("Не нашёл такой факт в памяти.", reply_markup=main_keyboard())
        return

    await message.answer("Удалил факт из памяти.", reply_markup=main_keyboard())


def is_nutrition_related(text: str, history=None) -> bool:
    if not text:
        return True

    normalized_text = text.lower().replace("ё", "е")
    nutrition_keywords = (
        "питан",
        "еда",
        "еду",
        "продукт",
        "блюд",
        "рацион",
        "съел",
        "съела",
        "съели",
        "съем",
        "поел",
        "поела",
        "завтрак",
        "обед",
        "ужин",
        "перекус",
        "овсян",
        "молок",
        "молочн",
        "салат",
        "творог",
        "йогурт",
        "кефир",
        "сыр",
        "яйц",
        "мяс",
        "куриц",
        "индейк",
        "рыб",
        "овощ",
        "фрукт",
        "растительн",
        "альтернатив",
        "заменител",
        "орех",
        "семен",
        "авокадо",
        "масл",
        "калори",
        "белк",
        "жир",
        "углевод",
        "сахар",
        "глютен",
        "лактоз",
        "аллерг",
        "витамин",
        "бад",
        "похуд",
        "вес",
        "масса",
    )

    if any(keyword in normalized_text for keyword in nutrition_keywords):
        return True

    history_text = " ".join([
        str(item.get("content", ""))
        for item in history or []
    ]).lower().replace("ё", "е")

    follow_up_keywords = (
        "подбери",
        "давай",
        "да",
        "хочу",
        "покажи",
        "расскажи",
        "посоветуй",
        "варианты",
        "подскажи",
        "можно",
        "что лучше",
    )

    if (
        history_text
        and len(normalized_text) <= 80
        and any(keyword in normalized_text for keyword in follow_up_keywords)
        and any(keyword in history_text for keyword in nutrition_keywords)
    ):
        return True

    try:
        response = openai_client.responses.create(
            model="gpt-4.1-mini",
            instructions="""
Ты классификатор.

Определи относится ли сообщение к:

- питанию
- еде
- продуктам
- здоровью
- нутрициологии
- витаминам
- минералам
- БАДам
- тренировкам
- восстановлению
- стрессу
- сну
- энергии
- метаболическому здоровью
- пищевым привычкам
- самочувствию после еды
- снижению веса
- набору массы
- анализу блюда
- списку съеденных продуктов
- описанию завтрака, обеда, ужина или перекуса

Верни строго одно слово:

YES

или

NO

Если сообщение содержит продукты, блюда или описание того, что пользователь съел или выпил, верни YES.
Если сообщение является коротким ответом на предыдущую реплику про питание, продукты или рекомендации, верни YES.
Если сомневаешься, верни YES.
""",
            input=f"""
Предыдущий контекст диалога:
{history_text or 'Нет контекста.'}

Текущее сообщение пользователя:
{text}
"""
        )

        result = response.output_text.strip().upper()
        return result == "YES"

    except Exception as e:
        print("CLASSIFIER ERROR:", repr(e))
        return True


async def analyze_food_photo(message: types.Message):
    telegram_id = message.from_user.id

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)

        image_base64 = base64.b64encode(file_bytes.read()).decode("utf-8")

        history = get_chat_history(telegram_id, limit=8)

        context_input = [
            build_user_memory_context(telegram_id)
        ] + history + [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Проанализируй фото еды. "
                            "Определи примерный состав блюда, баланс белков, жиров и углеводов, "
                            "влияние на насыщение, энергию, инсулин и метаболическое здоровье. "
                            "Если на фото не еда — вежливо скажи, что анализируешь только питание и близкие темы."
                        )
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{image_base64}"
                    }
                ]
            }
        ]

        response = openai_client.responses.create(
            model="gpt-4.1-mini",
            instructions=BOT_ROLE,
            input=context_input,
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [
                        OPENAI_VECTOR_STORE_ID
                    ]
                }
            ]
        )

        answer = response.output_text

        supabase.table("messages").insert({
            "telegram_id": telegram_id,
            "role": "user",
            "content": "[Фото еды]"
        }).execute()

        supabase.table("messages").insert({
            "telegram_id": telegram_id,
            "role": "assistant",
            "content": answer
        }).execute()

        supabase.table("meals").insert({
            "telegram_id": telegram_id,
            "text": "[Фото еды]",
            "ai_comment": answer
        }).execute()

        await message.answer(answer, reply_markup=main_keyboard())

    except Exception as e:
        print("PHOTO ANALYSIS ERROR:", repr(e))
        await message.answer(
            "Не смог проанализировать фото. Попробуй отправить другое изображение или описать еду текстом.",
            reply_markup=main_keyboard()
        )


@dp.message(Command("start"))
async def start(message: types.Message):
    telegram_id = message.from_user.id
    name = message.from_user.full_name

    try:
        supabase.table("users").upsert({
            "telegram_id": telegram_id,
            "name": name
        }).execute()
    except Exception as e:
        print("SUPABASE USER ERROR:", repr(e))

    await message.answer(
        "👋 Добро пожаловать в MealAdvisor!\n\n"
        "Я — AI-нутрициолог, который помогает разбираться в питании "
        "и делать более осознанный выбор.\n\n"
        f"{help_text()}",
        reply_markup=main_keyboard()
    )


@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(help_text(), reply_markup=main_keyboard())


@dp.message(Command("recipes"))
async def recipes_command(message: types.Message):
    PENDING_ACTIONS.pop(message.from_user.id, None)
    await send_recipe_book(message)


@dp.message(Command("feedback"))
async def feedback_command(message: types.Message):
    PENDING_ACTIONS[message.from_user.id] = "feedback"
    await message.answer(
        "Напиши сообщение для разработчика. Я передам его в поддержку.",
        reply_markup=cancel_keyboard()
    )


@dp.message(Command("reply"))
async def reply_command(message: types.Message):
    await send_support_reply(message)


@dp.message(Command("send"))
async def send_command(message: types.Message):
    await send_support_direct_message(message)


@dp.message(Command("remember"))
async def remember_fact(message: types.Message):
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Напиши факт после команды.\n\n"
            "Например: /remember Я не ем молочные продукты",
            reply_markup=main_keyboard()
        )
        return

    fact = parts[1].strip()

    await save_memory_from_text(message, fact)


@dp.message(Command("forget"))
async def forget_fact(message: types.Message):
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Напиши номер факта из /memory или точный текст факта.\n\n"
            "Например: /forget 1",
            reply_markup=main_keyboard()
        )
        return

    value = parts[1].strip()

    await delete_memory_from_text(message, value)


@dp.message(lambda message: message.text == MENU_RECIPES)
async def menu_recipes(message: types.Message):
    PENDING_ACTIONS.pop(message.from_user.id, None)
    await send_recipe_book(message)


@dp.message(lambda message: message.text == MENU_MEMORY)
async def menu_memory(message: types.Message):
    PENDING_ACTIONS.pop(message.from_user.id, None)
    await show_memory(message)


@dp.message(lambda message: message.text == MENU_REMEMBER)
async def menu_remember(message: types.Message):
    PENDING_ACTIONS[message.from_user.id] = "remember"

    await message.answer(
        "Отправь факт, который нужно запомнить.\n\n"
        "Например: Я не ем молочные продукты",
        reply_markup=cancel_keyboard()
    )


@dp.message(lambda message: message.text == MENU_FORGET)
async def menu_forget(message: types.Message):
    facts = get_user_memory_facts(message.from_user.id)

    if not facts:
        await message.answer(
            "Пока я не сохранил долгосрочных фактов о тебе.",
            reply_markup=main_keyboard()
        )
        return

    PENDING_ACTIONS[message.from_user.id] = "forget"
    memory = "\n".join([
        f"{index}. {fact}"
        for index, fact in enumerate(facts, start=1)
    ])

    await message.answer(
        f"Вот что я помню:\n\n{memory}\n\n"
        "Отправь номер факта, который нужно удалить, или точный текст факта.",
        reply_markup=cancel_keyboard()
    )


@dp.message(lambda message: message.text == MENU_HELP)
async def menu_help(message: types.Message):
    PENDING_ACTIONS.pop(message.from_user.id, None)
    await message.answer(help_text(), reply_markup=main_keyboard())


@dp.message(lambda message: message.text == MENU_FEEDBACK)
async def menu_feedback(message: types.Message):
    PENDING_ACTIONS[message.from_user.id] = "feedback"
    await message.answer(
        "Напиши сообщение для разработчика. Я передам его в поддержку.",
        reply_markup=cancel_keyboard()
    )


@dp.callback_query(lambda callback: callback.data == "recipes:home")
async def recipes_home_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "Книга рецептов\n\nВыбери раздел или воспользуйся поиском.",
        reply_markup=recipe_categories_keyboard()
    )


@dp.callback_query(lambda callback: callback.data == "recipes:search")
async def recipes_search_callback(callback: types.CallbackQuery):
    PENDING_ACTIONS[callback.from_user.id] = "recipe_search"
    await callback.answer()
    await callback.message.answer(
        "Что ищем? Напиши название, ингредиент или тег.\n\n"
        "Например: креветки, завтрак, суп, тофу",
        reply_markup=main_keyboard()
    )


@dp.callback_query(lambda callback: (callback.data or "").startswith("recipes:cat:"))
async def recipes_category_callback(callback: types.CallbackQuery):
    category_id = callback.data.split(":", maxsplit=2)[2]
    title = get_category_title(category_id)
    recipes = recipes_by_category(category_id)

    await callback.answer()

    if not recipes:
        await callback.message.edit_text(
            f"{title}\n\nВ этом разделе пока нет рецептов.",
            reply_markup=recipe_categories_keyboard()
        )
        return

    await callback.message.edit_text(
        f"{title}\n\nВыбери рецепт:",
        reply_markup=recipe_list_keyboard(category_id)
    )


@dp.callback_query(lambda callback: (callback.data or "").startswith("recipes:view:"))
async def recipes_view_callback(callback: types.CallbackQuery):
    recipe_id = callback.data.split(":", maxsplit=2)[2]
    recipe = RECIPES.get(recipe_id)

    await callback.answer()

    if not recipe:
        await callback.message.edit_text(
            "Не нашёл этот рецепт. Вернись к разделам и выбери другой.",
            reply_markup=recipe_categories_keyboard()
        )
        return

    await callback.message.edit_text(
        format_recipe(recipe),
        reply_markup=recipe_detail_keyboard(recipe_id)
    )


@dp.message(lambda message: message.text == MENU_CANCEL)
async def menu_cancel(message: types.Message):
    PENDING_ACTIONS.pop(message.from_user.id, None)
    await message.answer("Ок, отменил действие.", reply_markup=main_keyboard())


@dp.message(lambda message: message.text and message.from_user.id in PENDING_ACTIONS)
async def handle_pending_action(message: types.Message):
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


@dp.message(Command("memory"))
async def show_memory(message: types.Message):
    telegram_id = message.from_user.id
    facts = get_user_memory_facts(telegram_id)

    if not facts:
        await message.answer(
            "Пока я не сохранил долгосрочных фактов о тебе.",
            reply_markup=main_keyboard()
        )
        return

    memory = "\n".join([
        f"{index}. {fact}"
        for index, fact in enumerate(facts, start=1)
    ])

    await message.answer(
        f"Вот что я помню:\n\n{memory}\n\n"
        "Чтобы удалить факт, напиши /forget и его номер.\n"
        "Чтобы добавить факт, напиши /remember и сам факт.",
        reply_markup=main_keyboard()
    )



@dp.message(lambda message: message.photo)
async def photo_handler(message: types.Message):
    await analyze_food_photo(message)


@dp.message()
async def analyze_food(message: types.Message):
    telegram_id = message.from_user.id
    text = message.text

    if not text:
        await message.answer(
            "Пока я умею анализировать только текст и фото еды.",
            reply_markup=main_keyboard()
        )
        return

    try:
        history = get_chat_history(telegram_id, limit=12)
    except Exception as e:
        print("CHAT HISTORY ERROR:", repr(e))
        history = []

    if not is_nutrition_related(text, history=history):
        await message.answer(
            "Я специализируюсь только на вопросах питания, здоровья, сна, тренировок и образа жизни.",
            reply_markup=main_keyboard()
        )
        return

    try:
        supabase.table("messages").insert({
            "telegram_id": telegram_id,
            "role": "user",
            "content": text
        }).execute()

        context_input = [
            build_user_memory_context(telegram_id)
        ] + history + [
            {
                "role": "user",
                "content": text
            }
        ]

        response = openai_client.responses.create(
            model="gpt-4.1-mini",
            instructions=BOT_ROLE,
            input=context_input,
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [
                        OPENAI_VECTOR_STORE_ID
                    ]
                }
            ]
        )

        answer = response.output_text

        supabase.table("messages").insert({
            "telegram_id": telegram_id,
            "role": "assistant",
            "content": answer
        }).execute()

        supabase.table("meals").insert({
            "telegram_id": telegram_id,
            "text": text,
            "ai_comment": answer
        }).execute()

        await message.answer(answer, reply_markup=main_keyboard())

    except Exception as e:
        print("OPENAI ERROR:", repr(e))
        await message.answer(
            "Не смог сейчас проанализировать сообщение.",
            reply_markup=main_keyboard()
        )


@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        print("TELEGRAM UPDATE:", data)

        update = types.Update(**data)
        await dp.feed_update(bot, update)

        return {"ok": True}

    except Exception as e:
        print("WEBHOOK ERROR:", repr(e))
        return {"ok": False, "error": str(e)}
