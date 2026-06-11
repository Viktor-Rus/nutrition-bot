from aiogram import Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards import (
    MENU_MEMORY,
    cancel_keyboard,
    main_keyboard,
)
from services.memory import (
    delete_memory_from_text,
    get_user_memory_facts,
    save_memory_from_text,
)
from services.users import maybe_upsert_private_user
from state import PENDING_ACTIONS


def memory_actions_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Добавить факт",
                    callback_data="memory:remember"
                ),
                InlineKeyboardButton(
                    text="Удалить факт",
                    callback_data="memory:forget"
                ),
            ],
        ]
    )


async def show_memory(message: types.Message):
    telegram_id = message.from_user.id
    facts = get_user_memory_facts(telegram_id)

    if not facts:
        await message.answer(
            "Пока я не сохранил долгосрочных фактов о тебе.",
            reply_markup=memory_actions_keyboard()
        )
        return

    memory = "\n".join([
        f"{index}. {fact}"
        for index, fact in enumerate(facts, start=1)
    ])

    await message.answer(
        f"Вот что я знаю о тебе и буду учитывать при рекомендациях:\n\n{memory}\n\n"
        "Выбери действие:",
        reply_markup=memory_actions_keyboard()
    )


async def request_memory_fact(message: types.Message, user_id: int):
    PENDING_ACTIONS[user_id] = "remember"

    await message.answer(
        "Отправь факт, который нужно запомнить.\n\n"
        "Например: Я не ем молочные продукты",
        reply_markup=cancel_keyboard()
    )


async def request_memory_delete(message: types.Message, user_id: int):
    facts = get_user_memory_facts(user_id)

    if not facts:
        await message.answer(
            "Пока я не сохранил долгосрочных фактов о тебе.",
            reply_markup=memory_actions_keyboard()
        )
        return

    PENDING_ACTIONS[user_id] = "forget"
    memory = "\n".join([
        f"{index}. {fact}"
        for index, fact in enumerate(facts, start=1)
    ])

    await message.answer(
        f"Вот что я знаю о тебе и буду учитывать при рекомендациях:\n\n{memory}\n\n"
        "Отправь номер факта, который нужно удалить, или точный текст факта.",
        reply_markup=cancel_keyboard()
    )


def register(dp: Dispatcher):
    @dp.message(Command("remember"))
    async def remember_fact(message: types.Message):
        maybe_upsert_private_user(message)
        parts = (message.text or "").split(maxsplit=1)

        if len(parts) < 2 or not parts[1].strip():
            await message.answer(
                "Напиши факт после команды.\n\n"
                "Например: /remember Я не ем молочные продукты",
                reply_markup=main_keyboard()
            )
            return

        fact = parts[1].strip()

        await save_memory_from_text(message, fact)

    @dp.message(Command("forget"))
    async def forget_fact(message: types.Message):
        maybe_upsert_private_user(message)
        parts = (message.text or "").split(maxsplit=1)

        if len(parts) < 2 or not parts[1].strip():
            await message.answer(
                "Напиши номер факта из /memory или точный текст факта.\n\n"
                "Например: /forget 1",
                reply_markup=main_keyboard()
            )
            return

        value = parts[1].strip()

        await delete_memory_from_text(message, value)

    @dp.message(lambda message: message.text == MENU_MEMORY)
    async def menu_memory(message: types.Message):
        maybe_upsert_private_user(message)
        PENDING_ACTIONS.pop(message.from_user.id, None)
        await show_memory(message)

    @dp.message(Command("memory"))
    async def memory_command(message: types.Message):
        maybe_upsert_private_user(message)
        await show_memory(message)

    @dp.callback_query(lambda callback: callback.data == "memory:remember")
    async def memory_remember_callback(callback: types.CallbackQuery):
        await callback.answer()
        await request_memory_fact(callback.message, callback.from_user.id)

    @dp.callback_query(lambda callback: callback.data == "memory:forget")
    async def memory_forget_callback(callback: types.CallbackQuery):
        await callback.answer()
        await request_memory_delete(callback.message, callback.from_user.id)
