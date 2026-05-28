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

# Clients
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

openai_client = OpenAI(api_key=OPENAI_API_KEY)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

# FastAPI
app = FastAPI()


@app.get("/")
async def root():
    return {"status": "bot is running"}


# /start
@dp.message(Command("start"))
async def start(message: types.Message):

    telegram_id = message.from_user.id
    name = message.from_user.full_name

    supabase.table("users").upsert({
        "telegram_id": telegram_id,
        "name": name
    }).execute()

    await message.answer(
        "Привет 👋\n\n"
        "Я nutrition bot.\n"
        "Отправь мне что ты съел."
    )


# analyze meal
@dp.message()
async def analyze_food(message: types.Message):

    text = message.text

    prompt = f"""
Проанализируй прием пищи.

Еда:
{text}

Верни JSON:

{{
  "calories": 0,
  "protein": 0,
  "fat": 0,
  "carbs": 0,
  "comment": ""
}}
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Ты nutrition assistant."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    result = response.choices[0].message.content

    try:
        data = json.loads(result)

        supabase.table("meals").insert({
            "telegram_id": message.from_user.id,
            "text": text,
            "calories": data["calories"],
            "protein": data["protein"],
            "fat": data["fat"],
            "carbs": data["carbs"],
            "ai_comment": data["comment"]
        }).execute()

        await message.answer(
            f"""
🍽 Калории: {data['calories']}
🥩 Белки: {data['protein']}
🧈 Жиры: {data['fat']}
🍞 Углеводы: {data['carbs']}

💬 {data['comment']}
"""
        )

    except Exception as e:
        print(e)
        await message.answer("Ошибка анализа еды")


# webhook
@app.post("/webhook")
async def telegram_webhook(request: Request):

    data = await request.json()

    update = types.Update(**data)

    await dp.feed_update(bot, update)

    return {"ok": True}