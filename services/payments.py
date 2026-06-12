from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice

from clients import bot, supabase
from config import (
    PAYMENT_AMOUNT,
    PAYMENT_CURRENCY,
    PAYMENT_DESCRIPTION,
    PAYMENT_LABEL,
    PAYMENT_PROVIDER_DATA,
    PAYMENT_TITLE,
    YOOKASSA_PROVIDER_TOKEN,
)
from keyboards import main_keyboard


PAYMENT_PAYLOAD = "mealadvisor_premium"
PAYMENT_CALLBACK = "payments:mealadvisor_premium"


def format_payment_amount():
    if PAYMENT_CURRENCY == "RUB":
        rubles = PAYMENT_AMOUNT // 100
        kopecks = PAYMENT_AMOUNT % 100

        if kopecks:
            return f"{rubles:,}.{kopecks:02d} ₽".replace(",", " ")

        return f"{rubles:,} ₽".replace(",", " ")

    return f"{PAYMENT_AMOUNT} {PAYMENT_CURRENCY}"


def start_offer_text():
    return (
        "🔥 MealAdvisor — твой AI-помощник по питанию\n\n"
        "🥗 Анализируй еду по фото и тексту\n"
        "🧠 Сохраняй факты о себе\n"
        "📚 Используй книгу рецептов\n"
        "💡 Получай рекомендации с учётом твоих целей и ограничений\n\n"
        "Нажми кнопку ниже, чтобы оплатить доступ."
    )


def start_offer_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Оплатить {format_payment_amount()}",
                    callback_data=PAYMENT_CALLBACK
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


async def send_payment_invoice(message: types.Message):
    if not YOOKASSA_PROVIDER_TOKEN:
        await message.answer(
            "Оплата временно недоступна. Не настроен YooKassa provider token.",
            reply_markup=main_keyboard()
        )
        return

    await bot.send_invoice(
        chat_id=message.chat.id,
        title=PAYMENT_TITLE,
        description=PAYMENT_DESCRIPTION,
        payload=PAYMENT_PAYLOAD,
        provider_token=YOOKASSA_PROVIDER_TOKEN,
        currency=PAYMENT_CURRENCY,
        prices=[
            LabeledPrice(
                label=PAYMENT_LABEL,
                amount=PAYMENT_AMOUNT
            )
        ],
        provider_data=PAYMENT_PROVIDER_DATA,
        need_email=True,
        send_email_to_provider=True,
        start_parameter=PAYMENT_PAYLOAD,
    )


async def answer_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    if pre_checkout_query.invoice_payload != PAYMENT_PAYLOAD:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Не удалось проверить платёж. Попробуй начать оплату заново."
        )
        return

    if not YOOKASSA_PROVIDER_TOKEN:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Оплата временно недоступна. Попробуй позже."
        )
        return

    await pre_checkout_query.answer(ok=True)


def save_successful_payment(message: types.Message):
    payment = message.successful_payment

    if not payment:
        return

    try:
        supabase.table("payments").insert({
            "telegram_id": message.from_user.id,
            "currency": payment.currency,
            "total_amount": payment.total_amount,
            "invoice_payload": payment.invoice_payload,
            "telegram_payment_charge_id": payment.telegram_payment_charge_id,
            "provider_payment_charge_id": payment.provider_payment_charge_id,
        }).execute()
    except Exception as e:
        print("PAYMENT SAVE ERROR:", repr(e))


async def handle_successful_payment(message: types.Message):
    save_successful_payment(message)

    await message.answer(
        "Оплата прошла успешно. Спасибо!\n\n"
        "Теперь можно пользоваться MealAdvisor.",
        reply_markup=main_keyboard()
    )
