from aiogram import types

from clients import bot
from config import SUPPORT_CHAT_ID
from keyboards import main_keyboard


def is_support_chat(chat_id: int):
    return SUPPORT_CHAT_ID and str(chat_id) == str(SUPPORT_CHAT_ID)


async def send_feedback_to_support(message: types.Message, feedback_text: str):
    if not SUPPORT_CHAT_ID:
        await message.answer(
            "Обратная связь временно недоступна. Попробуй позже.",
            reply_markup=main_keyboard()
        )
        return

    user = message.from_user
    username = f"@{user.username}" if user.username else "не указан"
    full_name = user.full_name or "не указано"

    support_message = (
        "Новое сообщение обратной связи\n\n"
        f"Пользователь: {full_name}\n"
        f"Username: {username}\n"
        f"Telegram ID: {user.id}\n\n"
        f"Сообщение:\n{feedback_text}"
    )

    try:
        await bot.send_message(chat_id=SUPPORT_CHAT_ID, text=support_message)
    except Exception as e:
        print("FEEDBACK SEND ERROR:", repr(e))
        await message.answer(
            "Не смог отправить сообщение. Попробуй ещё раз позже.",
            reply_markup=main_keyboard()
        )
        return

    await message.answer(
        "Спасибо! Я передал сообщение разработчику.",
        reply_markup=main_keyboard()
    )


async def send_support_message(message: types.Message, command: str, prefix: str = ""):
    if not is_support_chat(message.chat.id):
        await message.answer("Эта команда доступна только в чате поддержки.")
        return

    parts = (message.text or "").split(maxsplit=2)

    if len(parts) < 3:
        await message.answer(
            "Формат:\n\n"
            f"/{command} TELEGRAM_ID текст сообщения\n\n"
            f"Например: /{command} 367204483 Спасибо за сообщение!"
        )
        return

    user_id_text = parts[1].strip()
    message_text = parts[2].strip()

    if not user_id_text.isdigit() or not message_text:
        await message.answer(
            "Не понял ID пользователя или текст сообщения.\n\n"
            f"Пример: /{command} 367204483 Спасибо за сообщение!"
        )
        return

    outgoing_text = f"{prefix}\n\n{message_text}" if prefix else message_text

    try:
        await bot.send_message(
            chat_id=int(user_id_text),
            text=outgoing_text
        )
    except Exception as e:
        print("SUPPORT MESSAGE SEND ERROR:", repr(e))
        await message.answer(
            "Не смог отправить сообщение пользователю. "
            "Проверь Telegram ID и что пользователь уже писал боту."
        )
        return

    await message.answer("Сообщение отправлено пользователю.")


async def send_support_reply(message: types.Message):
    await send_support_message(
        message=message,
        command="reply",
        prefix="Ответ поддержки:"
    )


async def send_support_direct_message(message: types.Message):
    await send_support_message(message=message, command="send")
