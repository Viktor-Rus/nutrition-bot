import os

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


@dp.message()
async def analyze_food(message: types.Message):
    text = message.text

    if not text:
        await message.answer("Пока я умею анализировать только текст. Фото добавим следующим шагом.")
        return

    try:
        response = openai_client.responses.create(
            model="gpt-4.1-mini",
            instructions=BOT_ROLE,
            input=text,
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

        try:
            supabase.table("meals").insert({
                "telegram_id": message.from_user.id,
                "text": text,
                "ai_comment": answer
            }).execute()
        except Exception as e:
            print("SUPABASE MEAL ERROR:", repr(e))

        await message.answer(answer)

    except Exception as e:
        print("OPENAI ERROR:", repr(e))
        await message.answer(
            "Не смог сейчас проанализировать сообщение. Проверь OPENAI_API_KEY и OPENAI_VECTOR_STORE_ID."
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