from aiogram import types

from services.payments import (
    format_amount,
    get_subscription,
    is_subscription_active,
    start_offer_keyboard,
)


def has_active_subscription(telegram_id: int):
    try:
        return is_subscription_active(get_subscription(telegram_id))
    except Exception as e:
        print("SUBSCRIPTION ACCESS CHECK ERROR:", repr(e))
        return False


async def require_subscription(
    message: types.Message,
    telegram_id: int,
    feature_name: str,
):
    if has_active_subscription(telegram_id):
        return True

    await message.answer(
        f"Функция «{feature_name}» доступна после подключения подписки.\n\n"
        f"Можно подключить 7 дней бесплатно, затем {format_amount()} в месяц.",
        reply_markup=start_offer_keyboard()
    )
    return False


async def require_recipes_subscription(message: types.Message, telegram_id: int):
    return await require_subscription(message, telegram_id, "Книга рецептов")


async def require_food_analysis_subscription(message: types.Message, telegram_id: int):
    return await require_subscription(message, telegram_id, "Анализ еды")


async def require_subscription_callback(callback: types.CallbackQuery, feature_name: str):
    if has_active_subscription(callback.from_user.id):
        return True

    await callback.answer(f"Функция «{feature_name}» доступна после подключения подписки.")
    await callback.message.answer(
        f"Функция «{feature_name}» доступна после подключения подписки.\n\n"
        f"Можно подключить 7 дней бесплатно, затем {format_amount()} в месяц.",
        reply_markup=start_offer_keyboard()
    )
    return False


async def require_recipes_subscription_callback(callback: types.CallbackQuery):
    return await require_subscription_callback(callback, "Книга рецептов")
