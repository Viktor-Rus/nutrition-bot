import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import requests
from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dateutil.relativedelta import relativedelta

from clients import bot, supabase
from config import (
    APP_BASE_URL,
    PAYMENT_CURRENCY,
    SUBSCRIPTION_MONTHLY_AMOUNT,
    SUBSCRIPTION_TRIAL_DAYS,
    YOOKASSA_SECRET_KEY,
    YOOKASSA_SHOP_ID,
)
from keyboards import main_keyboard


SUBSCRIPTION_START_CALLBACK = "subscriptions:start"
SUBSCRIPTION_STATUS_CALLBACK = "subscriptions:status"
SUBSCRIPTION_CANCEL_CALLBACK = "subscriptions:cancel"
SUBSCRIPTION_PAYLOAD = "mealadvisor_subscription"
YOOKASSA_API_URL = "https://api.yookassa.ru/v3"


def now_utc():
    return datetime.now(timezone.utc)


def parse_dt(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    normalized = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def iso_dt(value):
    if not value:
        return None

    return value.astimezone(timezone.utc).isoformat()


def format_amount(amount_minor=SUBSCRIPTION_MONTHLY_AMOUNT):
    if PAYMENT_CURRENCY == "RUB":
        rubles = amount_minor // 100
        kopecks = amount_minor % 100

        if kopecks:
            return f"{rubles:,}.{kopecks:02d} ₽".replace(",", " ")

        return f"{rubles:,} ₽".replace(",", " ")

    return f"{amount_minor} {PAYMENT_CURRENCY}"


def amount_to_yookassa_value(amount_minor):
    return str(Decimal(amount_minor) / Decimal(100))


def yookassa_is_configured():
    return bool(YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY and APP_BASE_URL)


def yookassa_headers():
    return {
        "Idempotence-Key": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def yookassa_request(method, path, payload=None):
    if not yookassa_is_configured():
        raise RuntimeError("YooKassa API credentials or APP_BASE_URL are not configured")

    response = requests.request(
        method=method,
        url=f"{YOOKASSA_API_URL}{path}",
        auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
        headers=yookassa_headers(),
        json=payload,
        timeout=20,
    )

    if response.status_code >= 400:
        raise RuntimeError(f"YooKassa API error {response.status_code}: {response.text}")

    return response.json()


def create_payment_method(telegram_id: int):
    payload = {
        "type": "bank_card",
        "confirmation": {
            "type": "redirect",
            "return_url": f"{APP_BASE_URL}/subscriptions/return?telegram_id={telegram_id}"
        },
        "metadata": {
            "telegram_id": str(telegram_id),
            "payload": SUBSCRIPTION_PAYLOAD,
        },
    }

    return yookassa_request("POST", "/payment_methods", payload)


def get_payment_method(payment_method_id: str):
    return yookassa_request("GET", f"/payment_methods/{payment_method_id}")


def create_recurring_payment(subscription):
    telegram_id = subscription["telegram_id"]
    payment_method_id = subscription["payment_method_id"]

    payload = {
        "amount": {
            "value": amount_to_yookassa_value(SUBSCRIPTION_MONTHLY_AMOUNT),
            "currency": PAYMENT_CURRENCY,
        },
        "capture": True,
        "payment_method_id": payment_method_id,
        "description": f"MealAdvisor Premium, подписка на 1 месяц для Telegram ID {telegram_id}",
        "metadata": {
            "telegram_id": str(telegram_id),
            "subscription_id": str(subscription.get("id") or ""),
            "payload": SUBSCRIPTION_PAYLOAD,
        },
    }

    return yookassa_request("POST", "/payments", payload)


def start_offer_text():
    return (
        "🔥 MealAdvisor — твой AI-помощник по питанию\n\n"
        "🥗 Анализируй еду по фото и тексту\n"
        "🧠 Сохраняй факты о себе\n"
        "📚 Используй книгу рецептов\n"
        "💡 Получай рекомендации с учётом твоих целей и ограничений\n\n"
        f"Первая неделя бесплатно, затем {format_amount()} в месяц. "
        "Карту нужно привязать сразу, списание начнётся после пробного периода."
    )


def start_offer_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подключить 7 дней бесплатно",
                    callback_data=SUBSCRIPTION_START_CALLBACK
                )
            ],
            [
                InlineKeyboardButton(
                    text="Статус подписки",
                    callback_data=SUBSCRIPTION_STATUS_CALLBACK
                )
            ],
            [
                InlineKeyboardButton(
                    text="Книга рецептов",
                    callback_data="recipes:home"
                )
            ],
        ]
    )


def subscription_manage_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Отменить подписку",
                    callback_data=SUBSCRIPTION_CANCEL_CALLBACK
                )
            ],
        ]
    )


def get_subscription(telegram_id: int):
    result = (
        supabase.table("subscriptions")
        .select("*")
        .eq("telegram_id", telegram_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    rows = result.data or []
    return rows[0] if rows else None


def upsert_subscription(row):
    return supabase.table("subscriptions").upsert(row).execute()


def update_subscription(telegram_id: int, fields):
    fields = dict(fields)
    fields["updated_at"] = iso_dt(now_utc())

    return (
        supabase.table("subscriptions")
        .update(fields)
        .eq("telegram_id", telegram_id)
        .execute()
    )


def save_pending_subscription(telegram_id: int, payment_method):
    upsert_subscription({
        "telegram_id": telegram_id,
        "payment_method_id": payment_method["id"],
        "status": "pending_confirmation",
        "trial_starts_at": None,
        "trial_ends_at": None,
        "current_period_ends_at": None,
        "next_charge_at": None,
        "last_error": None,
        "updated_at": iso_dt(now_utc()),
    })


def activate_subscription(telegram_id: int, payment_method_id: str):
    existing_subscription = get_subscription(telegram_id)

    if existing_subscription and existing_subscription.get("status") in ("trialing", "active"):
        return

    started_at = now_utc()
    trial_ends_at = started_at + timedelta(days=SUBSCRIPTION_TRIAL_DAYS)

    update_subscription(
        telegram_id,
        {
            "payment_method_id": payment_method_id,
            "status": "trialing",
            "trial_starts_at": iso_dt(started_at),
            "trial_ends_at": iso_dt(trial_ends_at),
            "current_period_ends_at": iso_dt(trial_ends_at),
            "next_charge_at": iso_dt(trial_ends_at),
            "last_error": None,
        }
    )


def cancel_subscription(telegram_id: int):
    update_subscription(
        telegram_id,
        {
            "status": "canceled",
            "canceled_at": iso_dt(now_utc()),
            "next_charge_at": None,
        }
    )


def is_subscription_active(subscription):
    if not subscription:
        return False

    if subscription.get("status") not in ("trialing", "active"):
        return False

    period_ends_at = parse_dt(subscription.get("current_period_ends_at"))
    return not period_ends_at or period_ends_at > now_utc()


def format_subscription_status(subscription):
    if not subscription:
        return (
            "Подписка не подключена.\n\n"
            f"Можно подключить 7 дней бесплатно, затем {format_amount()} в месяц."
        )

    status = subscription.get("status")
    trial_ends_at = parse_dt(subscription.get("trial_ends_at"))
    next_charge_at = parse_dt(subscription.get("next_charge_at"))

    if status == "pending_confirmation":
        return "Подписка ожидает привязки карты. Заверши привязку по ссылке ЮKassa."

    if status == "trialing":
        return (
            "Подписка активна: бесплатная неделя.\n\n"
            f"Пробный период до: {trial_ends_at:%d.%m.%Y %H:%M UTC}\n"
            f"Первое списание: {next_charge_at:%d.%m.%Y %H:%M UTC}\n"
            f"Сумма: {format_amount()} в месяц."
        )

    if status == "active":
        return (
            "Подписка активна.\n\n"
            f"Следующее списание: {next_charge_at:%d.%m.%Y %H:%M UTC}\n"
            f"Сумма: {format_amount()} в месяц."
        )

    if status == "past_due":
        return (
            "Подписка приостановлена: не удалось списать оплату.\n\n"
            "Можно попробовать подключить подписку заново."
        )

    if status == "canceled":
        return "Подписка отменена. Автосписаний больше не будет."

    return f"Статус подписки: {status or 'неизвестно'}"


async def start_subscription(message: types.Message, telegram_id: int):
    if not yookassa_is_configured():
        await message.answer(
            "Подписка временно недоступна. Не настроены параметры ЮKassa или APP_BASE_URL.",
            reply_markup=main_keyboard()
        )
        return

    subscription = get_subscription(telegram_id)

    if is_subscription_active(subscription):
        await message.answer(
            format_subscription_status(subscription),
            reply_markup=subscription_manage_keyboard()
        )
        return

    try:
        payment_method = create_payment_method(telegram_id)
        save_pending_subscription(telegram_id, payment_method)
    except Exception as e:
        print("SUBSCRIPTION START ERROR:", repr(e))
        await message.answer(
            "Не смог создать ссылку для привязки карты. Попробуй позже.",
            reply_markup=main_keyboard()
        )
        return

    confirmation_url = (payment_method.get("confirmation") or {}).get("confirmation_url")

    if not confirmation_url:
        await message.answer(
            "ЮKassa не вернула ссылку для привязки карты. Попробуй позже.",
            reply_markup=main_keyboard()
        )
        return

    await message.answer(
        "Чтобы включить бесплатную неделю, привяжи карту в ЮKassa.\n\n"
        f"Сейчас списания не будет. Через {SUBSCRIPTION_TRIAL_DAYS} дней начнётся подписка "
        f"{format_amount()} в месяц.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Привязать карту",
                        url=confirmation_url
                    )
                ]
            ]
        )
    )


async def send_subscription_status(message: types.Message, telegram_id: int):
    subscription = get_subscription(telegram_id)
    reply_markup = subscription_manage_keyboard() if is_subscription_active(subscription) else start_offer_keyboard()

    await message.answer(
        format_subscription_status(subscription),
        reply_markup=reply_markup
    )


async def cancel_user_subscription(message: types.Message, telegram_id: int):
    subscription = get_subscription(telegram_id)

    if not subscription or subscription.get("status") == "canceled":
        await message.answer("У тебя нет активной подписки.", reply_markup=main_keyboard())
        return

    cancel_subscription(telegram_id)

    await message.answer(
        "Подписка отменена. Автосписаний больше не будет.",
        reply_markup=main_keyboard()
    )


async def handle_payment_method_active(payment_method):
    metadata = payment_method.get("metadata") or {}
    telegram_id = metadata.get("telegram_id")

    if not telegram_id:
        return

    if payment_method.get("status") != "active" or not payment_method.get("saved"):
        return

    telegram_id = int(telegram_id)
    activate_subscription(telegram_id, payment_method["id"])

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=(
                "Карта привязана. Бесплатная неделя активирована.\n\n"
                f"Первое списание {format_amount()} будет через {SUBSCRIPTION_TRIAL_DAYS} дней."
            ),
            reply_markup=main_keyboard()
        )
    except Exception as e:
        print("SUBSCRIPTION ACTIVATION MESSAGE ERROR:", repr(e))


def save_subscription_payment(payment, status):
    metadata = payment.get("metadata") or {}
    telegram_id = metadata.get("telegram_id")

    if not telegram_id:
        return

    try:
        supabase.table("subscription_payments").insert({
            "telegram_id": int(telegram_id),
            "yookassa_payment_id": payment.get("id"),
            "status": status,
            "amount": (payment.get("amount") or {}).get("value"),
            "currency": (payment.get("amount") or {}).get("currency"),
            "raw": payment,
        }).execute()
    except Exception as e:
        print("SUBSCRIPTION PAYMENT SAVE ERROR:", repr(e))


async def handle_recurring_payment_succeeded(payment):
    metadata = payment.get("metadata") or {}
    telegram_id = metadata.get("telegram_id")

    if not telegram_id:
        return

    telegram_id = int(telegram_id)
    subscription = get_subscription(telegram_id)
    current_end = parse_dt(subscription.get("current_period_ends_at")) if subscription else None
    base_date = max(current_end or now_utc(), now_utc())
    next_charge_at = base_date + relativedelta(months=1)

    update_subscription(
        telegram_id,
        {
            "status": "active",
            "current_period_ends_at": iso_dt(next_charge_at),
            "next_charge_at": iso_dt(next_charge_at),
            "last_payment_id": payment.get("id"),
            "last_error": None,
        }
    )
    save_subscription_payment(payment, "succeeded")

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=(
                "Оплата подписки прошла успешно.\n\n"
                f"Следующее списание: {next_charge_at:%d.%m.%Y}."
            ),
            reply_markup=main_keyboard()
        )
    except Exception as e:
        print("RECURRING PAYMENT SUCCESS MESSAGE ERROR:", repr(e))


async def handle_recurring_payment_canceled(payment):
    metadata = payment.get("metadata") or {}
    telegram_id = metadata.get("telegram_id")

    if not telegram_id:
        return

    telegram_id = int(telegram_id)
    cancellation_details = payment.get("cancellation_details") or {}

    update_subscription(
        telegram_id,
        {
            "status": "past_due",
            "last_payment_id": payment.get("id"),
            "last_error": cancellation_details.get("reason") or "payment_canceled",
        }
    )
    save_subscription_payment(payment, "canceled")

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=(
                "Не удалось списать оплату за подписку.\n\n"
                "Подписка временно приостановлена. Можно подключить её заново через /start."
            ),
            reply_markup=main_keyboard()
        )
    except Exception as e:
        print("RECURRING PAYMENT CANCEL MESSAGE ERROR:", repr(e))


async def handle_yookassa_event(payload):
    event = payload.get("event")
    obj = payload.get("object") or {}

    if event == "payment_method.active":
        await handle_payment_method_active(obj)
        return {"ok": True}

    if event == "payment.succeeded" and (obj.get("metadata") or {}).get("payload") == SUBSCRIPTION_PAYLOAD:
        await handle_recurring_payment_succeeded(obj)
        return {"ok": True}

    if event == "payment.canceled" and (obj.get("metadata") or {}).get("payload") == SUBSCRIPTION_PAYLOAD:
        await handle_recurring_payment_canceled(obj)
        return {"ok": True}

    return {"ok": True, "ignored": True}


def activate_subscription_from_return(telegram_id: int = None, payment_method_id: str = None):
    if not payment_method_id and telegram_id:
        subscription = get_subscription(telegram_id)
        payment_method_id = subscription.get("payment_method_id") if subscription else None

    if not payment_method_id:
        return False

    payment_method = get_payment_method(payment_method_id)
    metadata = payment_method.get("metadata") or {}
    metadata_telegram_id = metadata.get("telegram_id")
    resolved_telegram_id = telegram_id or metadata_telegram_id

    if (
        resolved_telegram_id
        and payment_method.get("status") == "active"
        and payment_method.get("saved")
    ):
        activate_subscription(int(resolved_telegram_id), payment_method["id"])
        return True

    return False


def get_due_subscriptions(limit=50):
    result = (
        supabase.table("subscriptions")
        .select("*")
        .in_("status", ["trialing", "active"])
        .lte("next_charge_at", iso_dt(now_utc()))
        .limit(limit)
        .execute()
    )

    return result.data or []


async def charge_due_subscriptions(limit=50):
    due_subscriptions = get_due_subscriptions(limit=limit)
    charged = 0
    failed = 0

    for subscription in due_subscriptions:
        telegram_id = subscription["telegram_id"]

        try:
            payment = create_recurring_payment(subscription)
        except Exception as e:
            failed += 1
            print("RECURRING PAYMENT CREATE ERROR:", telegram_id, repr(e))
            update_subscription(
                telegram_id,
                {
                    "status": "past_due",
                    "last_error": str(e)[:500],
                }
            )
            continue

        payment_status = payment.get("status")

        if payment_status == "succeeded":
            charged += 1
            await handle_recurring_payment_succeeded(payment)
        elif payment_status == "canceled":
            failed += 1
            await handle_recurring_payment_canceled(payment)
        else:
            update_subscription(
                telegram_id,
                {
                    "last_payment_id": payment.get("id"),
                    "last_error": f"Unexpected payment status: {payment_status}",
                }
            )

    return {
        "ok": True,
        "due": len(due_subscriptions),
        "charged": charged,
        "failed": failed,
    }
