import asyncio

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from aiogram import types

from clients import bot, dp
from handlers.registry import register_handlers
from keyboards import BOT_COMMANDS
from config import ALLOWED_TELEGRAM_IDS, SUBSCRIPTION_CRON_SECRET
from services.payments import (
    activate_subscription_from_return,
    charge_due_subscriptions,
    handle_yookassa_event,
)


app = FastAPI()

register_handlers(dp)


def get_update_user_id(data):
    for key in (
        "message",
        "edited_message",
        "callback_query",
        "pre_checkout_query",
        "shipping_query",
    ):
        event = data.get(key)

        if not event:
            continue

        user = event.get("from")

        if user and user.get("id"):
            return int(user["id"])

    return None


def get_update_chat_id(data):
    message = data.get("message") or data.get("edited_message")

    if message and message.get("chat") and message["chat"].get("id"):
        return int(message["chat"]["id"])

    callback_query = data.get("callback_query")

    if callback_query:
        message = callback_query.get("message") or {}
        chat = message.get("chat") or {}

        if chat.get("id"):
            return int(chat["id"])

    return None


async def reject_disallowed_user(data):
    if not ALLOWED_TELEGRAM_IDS:
        return False

    user_id = get_update_user_id(data)

    if user_id in ALLOWED_TELEGRAM_IDS:
        return False

    chat_id = get_update_chat_id(data)

    if chat_id:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="Бот временно недоступен. Идёт закрытое тестирование."
            )
        except Exception as e:
            print("ALLOWLIST REJECT MESSAGE ERROR:", repr(e))

    print("DISALLOWED TELEGRAM USER:", user_id)
    return True


@app.get("/")
async def root():
    return {"status": "bot is running"}


@app.get("/subscriptions/return", response_class=HTMLResponse)
async def subscription_return(
    telegram_id: int = None,
    payment_method_id: str = None,
):
    try:
        activation_result = activate_subscription_from_return(
            telegram_id=telegram_id,
            payment_method_id=payment_method_id,
        )
    except Exception as e:
        print("SUBSCRIPTION RETURN ERROR:", repr(e))
        activation_result = None

    if activation_result == "trial_activated":
        return """
        <html>
            <body>
                <h2>Карта привязана</h2>
                <p>Бесплатная неделя активирована. Можно вернуться в Telegram.</p>
            </body>
        </html>
        """

    if activation_result == "paid_active":
        return """
        <html>
            <body>
                <h2>Подписка активна</h2>
                <p>Оплата прошла успешно. Можно вернуться в Telegram.</p>
            </body>
        </html>
        """

    if activation_result == "payment_pending":
        return """
        <html>
            <body>
                <h2>Карта привязана</h2>
                <p>Оплата подписки обрабатывается. Результат придёт в Telegram.</p>
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


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(setup_bot_menu())


async def setup_bot_menu():
    try:
        await bot.set_my_commands(BOT_COMMANDS)
    except Exception as e:
        print("BOT MENU SETUP ERROR:", repr(e))


@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        print("TELEGRAM UPDATE:", data)

        if await reject_disallowed_user(data):
            return {"ok": True, "blocked": True}

        update = types.Update(**data)
        await dp.feed_update(bot, update)

        return {"ok": True}

    except Exception as e:
        print("WEBHOOK ERROR:", repr(e))
        return {"ok": False, "error": str(e)}
