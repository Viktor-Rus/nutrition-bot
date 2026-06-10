import os
import json
import base64

from dotenv import load_dotenv
from fastapi import FastAPI, Request

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from openai import OpenAI
from supabase import create_client

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_VECTOR_STORE_ID = os.getenv("OPENAI_VECTOR_STORE_ID")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

openai_client = OpenAI(api_key=OPENAI_API_KEY)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

app = FastAPI()


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


@app.get("/")
async def root():
    return {"status": "bot is running"}


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


def extract_and_save_memory(telegram_id: int, user_message: str, assistant_answer: str):
    try:
        response = openai_client.responses.create(
            model="gpt-4.1-mini",
            instructions="""
Ты извлекаешь долгосрочную память о пользователе для AI-нутрициолога.

Сохраняй только факты, которые могут быть полезны в будущем:
- цели
- пищевые предпочтения
- ограничения
- аллергии
- режим питания
- реакции на еду
- сон
- стресс
- тренировки
- хронические жалобы
- привычки

Не сохраняй разовые блюда вроде "съел суп".
Не сохраняй временные факты без долгосрочной пользы.

Верни строго JSON:
{
  "facts": ["факт 1", "факт 2"]
}

Если фактов нет:
{
  "facts": []
}
""",
            input=f"""
Сообщение пользователя:
{user_message}

Ответ ассистента:
{assistant_answer}
"""
        )

        try:
            data = json.loads(response.output_text)
        except Exception as e:
            print("MEMORY JSON ERROR:", repr(e), response.output_text)
            return

        facts = data.get("facts", [])

        for fact in facts:
            if not fact:
                continue

            fact = fact.strip()

            if len(fact) < 10:
                continue

            save_user_memory_fact(telegram_id, fact)

    except Exception as e:
        print("MEMORY EXTRACTION ERROR:", repr(e))


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

        await message.answer(answer)

        extract_and_save_memory(
            telegram_id=telegram_id,
            user_message="[Фото еды]",
            assistant_answer=answer
        )

    except Exception as e:
        print("PHOTO ANALYSIS ERROR:", repr(e))
        await message.answer(
            "Не смог проанализировать фото. Попробуй отправить другое изображение или описать еду текстом."
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
"Я — AI-нутрициолог, который помогает разбираться в питании и делать более осознанный выбор.\n\n"
"Что я умею:\n\n"
"📸 Анализировать еду по фото\n"
"🥗 Анализировать блюда и продукты по описанию\n"
"📦 Разбирать состав продуктов по фото упаковки\n"
"🌍 Переводить составы с английского и других языков на русский\n"
"💡 Давать персональные рекомендации по питанию и привычкам\n"
"🧠 Запоминать важные факты через /remember\n"
"🗑 Удалять факты из памяти через /forget\n"
"📷 Отправьте фото блюда, упаковки продукта или задайте вопрос о питании — и я помогу разобраться 💚"
    )


@dp.message(Command("remember"))
async def remember_fact(message: types.Message):
    telegram_id = message.from_user.id
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Напиши факт после команды.\n\n"
            "Например: /remember Я не ем молочные продукты"
        )
        return

    fact = parts[1].strip()

    try:
        status = save_user_memory_fact(telegram_id, fact)
    except Exception as e:
        print("MANUAL MEMORY SAVE ERROR:", repr(e))
        await message.answer("Не смог сохранить факт в память. Попробуй ещё раз.")
        return

    if status == "duplicate":
        await message.answer("Этот факт уже есть в моей памяти.")
        return

    await message.answer("Запомнил. Посмотреть сохранённое можно через /memory.")


@dp.message(Command("forget"))
async def forget_fact(message: types.Message):
    telegram_id = message.from_user.id
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Напиши номер факта из /memory или точный текст факта.\n\n"
            "Например: /forget 1"
        )
        return

    value = parts[1].strip()

    try:
        if value.isdigit():
            facts = get_user_memory_facts(telegram_id)
            index = int(value)

            if index < 1 or index > len(facts):
                await message.answer("Не нашёл факт с таким номером. Проверь список через /memory.")
                return

            fact = facts[index - 1]
        else:
            fact = value

        status = delete_user_memory_fact(telegram_id, fact)
    except Exception as e:
        print("MANUAL MEMORY DELETE ERROR:", repr(e))
        await message.answer("Не смог удалить факт из памяти. Попробуй ещё раз.")
        return

    if status == "not_found":
        await message.answer("Не нашёл такой факт в памяти.")
        return

    await message.answer("Удалил факт из памяти.")


@dp.message(Command("memory"))
async def show_memory(message: types.Message):
    telegram_id = message.from_user.id
    facts = get_user_memory_facts(telegram_id)

    if not facts:
        await message.answer("Пока я не сохранил долгосрочных фактов о тебе.")
        return

    memory = "\n".join([
        f"{index}. {fact}"
        for index, fact in enumerate(facts, start=1)
    ])

    await message.answer(
        f"Вот что я помню:\n\n{memory}\n\n"
        "Чтобы удалить факт, напиши /forget и его номер.\n"
        "Чтобы добавить факт, напиши /remember и сам факт."
    )



@dp.message(lambda message: message.photo)
async def photo_handler(message: types.Message):
    await analyze_food_photo(message)


@dp.message()
async def analyze_food(message: types.Message):
    telegram_id = message.from_user.id
    text = message.text

    if not text:
        await message.answer("Пока я умею анализировать только текст и фото еды.")
        return

    try:
        history = get_chat_history(telegram_id, limit=12)
    except Exception as e:
        print("CHAT HISTORY ERROR:", repr(e))
        history = []

    if not is_nutrition_related(text, history=history):
        await message.answer(
            "Я специализируюсь только на вопросах питания, здоровья, сна, тренировок и образа жизни."
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

        await message.answer(answer)

        extract_and_save_memory(
            telegram_id=telegram_id,
            user_message=text,
            assistant_answer=answer
        )

    except Exception as e:
        print("OPENAI ERROR:", repr(e))
        await message.answer("Не смог сейчас проанализировать сообщение.")


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
