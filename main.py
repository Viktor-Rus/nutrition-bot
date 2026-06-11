from fastapi import FastAPI, Request

from aiogram import types

from clients import bot, dp
from handlers.registry import register_handlers
from keyboards import BOT_COMMANDS


app = FastAPI()

register_handlers(dp)


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
