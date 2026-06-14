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
SUBSCRIPTION_CANCEL_CONFIRM_CALLBACK = "subscriptions:cancel_confirm"
SUBSCRIPTION_CANCEL_KEEP_CALLBACK = "subscriptions:cancel_keep"
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


def has_used_trial(subscription):
    if not subscription:
        return False

    return bool(subscription.get("trial_starts_at") or subscription.get("trial_ends_at"))


def start_offer_text(subscription=None):
    if has_used_trial(subscription):
        return (
            "🔥 MealAdvisor — AI-проводник по питанию и привычкам\n\n"
            "🥗 Помогает улучшать приёмы пищи без жёстких запретов\n"
            "🧠 Учитывает твои цели, ограничения, предпочтения и сохранённые факты\n"
            "👣 Предлагает маленькие шаги вместо резких диет\n"
            "📚 Даёт доступ к книге рецептов\n\n"
            f"Бесплатный период уже был использован. Подписка стоит {format_amount()} в месяц. "
            "После привязки карты оплата спишется сразу."
        )

    return (
        "🔥 MealAdvisor — AI-проводник по питанию и привычкам\n\n"
        "🥗 Помогает улучшать приёмы пищи без жёстких запретов\n"
        "🧠 Учитывает твои цели, ограничения, предпочтения и сохранённые факты\n"
        "📝 Можно добавить: аллергии, продукты, которые ты не ешь, цели, режим, предпочтения\n"
        "👣 Предлагает маленькие шаги вместо резких диет\n"
        "🍔 Подсказывает, как снизить последствия менее полезной еды без чувства вины\n"
        "📚 Даёт доступ к книге рецептов\n\n"
        f"Первая неделя бесплатно, затем {format_amount()} в месяц. "
        "Карту нужно привязать сразу, списание начнётся после пробного периода."
    )


def start_offer_keyboard(subscription=None):
    start_button_text = (
        "Оплатить подписку"
        if has_used_trial(subscription)
        else "Подключить 7 дней бесплатно"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=start_button_text,
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


def subscription_cancel_confirmation_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, отменить подписку",
                    callback_data=SUBSCRIPTION_CANCEL_CONFIRM_CALLBACK
                )
            ],
            [
                InlineKeyboardButton(
                    text="Оставить подписку",
                    callback_data=SUBSCRIPTION_CANCEL_KEEP_CALLBACK
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
    return supabase.table("subscriptions").upsert(
        row,
        on_conflict="telegram_id",
    ).execute()


def update_subscription(telegram_id: int, fields):
    fields = dict(fields)
    fields["updated_at"] = iso_dt(now_utc())

    return (
        supabase.table("subscriptions")
        .update(fields)
        .eq("telegram_id", telegram_id)
        .execute()
    )


def save_pending_subscription(telegram_id: int, payment_method, existing_subscription=None):
    existing_subscription = existing_subscription or {}

    upsert_subscription({
        "telegram_id": telegram_id,
        "payment_method_id": payment_method["id"],
        "status": "pending_confirmation",
        "trial_starts_at": existing_subscription.get("trial_starts_at"),
        "trial_ends_at": existing_subscription.get("trial_ends_at"),
        "current_period_ends_at": existing_subscription.get("current_period_ends_at"),
        "next_charge_at": None,
        "last_error": None,
        "updated_at": iso_dt(now_utc()),
    })


def activate_subscription(telegram_id: int, payment_method_id: str):
    existing_subscription = get_subscription(telegram_id)

    if existing_subscription and existing_subscription.get("status") in ("trialing", "active"):
        return

    if has_used_trial(existing_subscription):
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

    period_ends_at = parse_dt(subscription.get("current_period_ends_at"))

    if subscription.get("status") in ("trialing", "active"):
        return not period_ends_at or period_ends_at > now_utc()

    if subscription.get("status") == "canceled":
        return bool(period_ends_at and period_ends_at > now_utc())

    return False


def is_subscription_auto_renewing(subscription):
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
    period_ends_at = parse_dt(subscription.get("current_period_ends_at"))

    if status == "pending_confirmation":
        if has_used_trial(subscription):
            return "Подписка ожидает привязки карты и оплаты. Заверши оплату по ссылке ЮKassa."

        return "Подписка ожидает привязки карты. Заверши привязку по ссылке ЮKassa."

    if status == "pending_payment":
        return "Оплата подписки обрабатывается. Доступ откроется после успешного платежа."

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
        if period_ends_at and period_ends_at > now_utc():
            return (
                "Подписка отменена. Автосписаний больше не будет.\n\n"
                f"Доступ сохранён до: {period_ends_at:%d.%m.%Y %H:%M UTC}."
            )

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

    if is_subscription_auto_renewing(subscription):
        await message.answer(
            format_subscription_status(subscription),
            reply_markup=subscription_manage_keyboard()
        )
        return

    if is_subscription_active(subscription):
        await message.answer(
            format_subscription_status(subscription),
            reply_markup=main_keyboard()
        )
        return

    trial_used = has_used_trial(subscription)

    try:
        payment_method = create_payment_method(telegram_id)
        save_pending_subscription(telegram_id, payment_method, existing_subscription=subscription)
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

    if trial_used:
        await message.answer(
            "Чтобы подключить подписку, привяжи карту в ЮKassa.\n\n"
            "Бесплатный период уже был использован, поэтому после привязки карты "
            f"сразу спишется {format_amount()} за первый месяц.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Перейти к оплате",
                            url=confirmation_url
                        )
                    ]
                ]
            )
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
    reply_markup = (
        subscription_manage_keyboard()
        if is_subscription_auto_renewing(subscription)
        else start_offer_keyboard(subscription)
    )

    await message.answer(
        format_subscription_status(subscription),
        reply_markup=reply_markup
    )


async def request_subscription_cancel_confirmation(message: types.Message, telegram_id: int):
    subscription = get_subscription(telegram_id)

    if not is_subscription_auto_renewing(subscription):
        await message.answer("У тебя нет активной подписки.", reply_markup=main_keyboard())
        return

    period_ends_at = parse_dt(subscription.get("current_period_ends_at"))
    access_note = ""
    if period_ends_at:
        access_note = f"\n\nДоступ сохранится до: {period_ends_at:%d.%m.%Y %H:%M UTC}."

    await message.answer(
        "Ты уверен, что хочешь отменить подписку?\n\n"
        "После отмены автосписаний больше не будет, но доступ к платным функциям останется "
        "до конца уже оплаченного или пробного периода."
        f"{access_note}",
        reply_markup=subscription_cancel_confirmation_keyboard()
    )


async def cancel_user_subscription(message: types.Message, telegram_id: int):
    subscription = get_subscription(telegram_id)

    if not is_subscription_auto_renewing(subscription):
        await message.answer("У тебя нет активной подписки.", reply_markup=main_keyboard())
        return

    cancel_subscription(telegram_id)
    period_ends_at = parse_dt(subscription.get("current_period_ends_at"))
    access_note = ""
    if period_ends_at and period_ends_at > now_utc():
        access_note = f"\n\nДоступ сохранён до: {period_ends_at:%d.%m.%Y %H:%M UTC}."

    await message.answer(
        "Подписка отменена. Автосписаний больше не будет."
        f"{access_note}\n\n"
        "Спасибо, что пользовался MealAdvisor. Надеемся, сервис помог тебе лучше понимать питание "
        "и делать маленькие шаги к более комфортным привычкам.\n\n"
        "Будем рады снова видеть тебя, если захочешь вернуться.",
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
    subscription = get_subscription(telegram_id)

    if is_subscription_auto_renewing(subscription):
        return

    if has_used_trial(subscription) and subscription.get("status") == "pending_confirmation":
        update_subscription(
            telegram_id,
            {
                "payment_method_id": payment_method["id"],
                "status": "pending_payment",
                "last_error": None,
            }
        )

        try:
            payment = create_recurring_payment(get_subscription(telegram_id))
        except Exception as e:
            print("INITIAL SUBSCRIPTION PAYMENT ERROR:", repr(e))
            update_subscription(
                telegram_id,
                {
                    "status": "past_due",
                    "last_error": "initial_payment_create_failed",
                }
            )
            try:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=(
                        "Карта привязана, но не удалось списать оплату за подписку.\n\n"
                        "Попробуй подключить подписку ещё раз позже."
                    ),
                    reply_markup=main_keyboard()
                )
            except Exception as message_error:
                print("INITIAL PAYMENT ERROR MESSAGE ERROR:", repr(message_error))
            return

        payment_status = payment.get("status")

        if payment_status == "succeeded":
            await handle_recurring_payment_succeeded(payment)
            return

        if payment_status == "canceled":
            await handle_recurring_payment_canceled(payment)
            return

        save_subscription_payment(payment, payment_status or "pending")
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=(
                    "Карта привязана. Оплата подписки обрабатывается.\n\n"
                    "Доступ откроется после успешного платежа."
                ),
                reply_markup=main_keyboard()
            )
        except Exception as e:
            print("INITIAL PAYMENT PENDING MESSAGE ERROR:", repr(e))
        return

    if has_used_trial(subscription):
        return

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

    if subscription and subscription.get("last_payment_id") == payment.get("id"):
        return

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
        resolved_telegram_id = int(resolved_telegram_id)
        subscription = get_subscription(resolved_telegram_id)

        if has_used_trial(subscription):
            if subscription and subscription.get("status") == "active":
                return "paid_active"

            return "payment_pending"

        activate_subscription(resolved_telegram_id, payment_method["id"])
        return "trial_activated"

    return None


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
