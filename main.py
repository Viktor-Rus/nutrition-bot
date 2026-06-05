import os
import json

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


def get_user_memory(telegram_id: int):
    result = (
        supabase.table("user_memory")
        .select("fact")
        .eq("telegram_id", telegram_id)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )

    facts = result.data or []

    if not facts:
        return ""

    return "\n".join([f"- {item['fact']}" for item in facts])


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

            existing = (
                supabase.table("user_memory")
                .select("fact")
                .eq("telegram_id", telegram_id)
                .eq("fact", fact)
                .execute()
            )

            if existing.data:
                continue

            supabase.table("user_memory").insert({
                "telegram_id": telegram_id,
                "fact": fact
            }).execute()

    except Exception as e:
        print("MEMORY EXTRACTION ERROR:", repr(e))


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
        "Привет 👋\n\n"
        "Я твой AI-нутрициолог.\n"
        "Отправь мне описание еды, самочувствия или привычки — я помогу разобрать."
    )


@dp.message(Command("memory"))
async def show_memory(message: types.Message):
    telegram_id = message.from_user.id
    memory = get_user_memory(telegram_id)

    if not memory:
        await message.answer("Пока я не сохранил долгосрочных фактов о тебе.")
        return

    await message.answer(f"Вот что я помню:\n\n{memory}")


@dp.message()
async def analyze_food(message: types.Message):
    telegram_id = message.from_user.id
    text = message.text

    if not text:
        await message.answer("Пока я умею анализировать только текст. Фото добавим следующим шагом.")
        return

    try:
        supabase.table("messages").insert({
            "telegram_id": telegram_id,
            "role": "user",
            "content": text
        }).execute()

        history = get_chat_history(telegram_id, limit=12)
        memory = get_user_memory(telegram_id)

        context_input = [
            {
                "role": "system",
                "content": f"Долговременная память о пользователе:\n{memory or 'Пока нет сохранённых фактов.'}"
            }
        ] + history

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