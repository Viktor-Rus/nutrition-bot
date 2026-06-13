from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from aiogram import types

from clients import bot, dp
from handlers.registry import register_handlers
from keyboards import BOT_COMMANDS
from config import SUBSCRIPTION_CRON_SECRET
from services.payments import (
    activate_subscription_from_return,
    charge_due_subscriptions,
    handle_yookassa_event,
)


app = FastAPI()

register_handlers(dp)


@app.get("/")
async def root():
    return {"status": "bot is running"}


@app.get("/subscriptions/return", response_class=HTMLResponse)
async def subscription_return(
    telegram_id: int = None,
    payment_method_id: str = None,
):
    try:
        activated = activate_subscription_from_return(
            telegram_id=telegram_id,
            payment_method_id=payment_method_id,
        )
    except Exception as e:
        print("SUBSCRIPTION RETURN ERROR:", repr(e))
        activated = False

    if activated:
        return """
        <html>
            <body>
                <h2>Карта привязана</h2>
                <p>Бесплатная неделя активирована. Можно вернуться в Telegram.</p>
            </body>
        </html>
        """

    return """
    <html>
        <body>
            <h2>Проверяем привязку карты</h2>
            <p>Если ты уже завершил привязку, вернись в Telegram. Обычно подтверждение приходит в течение нескольких секунд.</p>
        </body>
    </html>
    """


@app.post("/yookassa/webhook")
async def yookassa_webhook(request: Request):
    try:
        data = await request.json()
        print("YOOKASSA EVENT:", data)
        return await handle_yookassa_event(data)
    except Exception as e:
        print("YOOKASSA WEBHOOK ERROR:", repr(e))
        return {"ok": False, "error": str(e)}


@app.post("/subscriptions/charge-due")
async def charge_due_subscriptions_endpoint(request: Request):
    if SUBSCRIPTION_CRON_SECRET:
        provided_secret = request.headers.get("x-cron-secret") or request.query_params.get("secret")

        if provided_secret != SUBSCRIPTION_CRON_SECRET:
            raise HTTPException(status_code=403, detail="Forbidden")

    return await charge_due_subscriptions()


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
