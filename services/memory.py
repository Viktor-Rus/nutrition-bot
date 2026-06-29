from aiogram import types

from clients import supabase
from keyboards import MENU_MEMORY, main_keyboard


def get_chat_history(telegram_id: int, limit: int = 10):
    result = (
        supabase.table("messages")
        .select("role, content")
        .eq("telegram_id", telegram_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    rows = result.data or []
    rows.reverse()

    return rows


def get_user_memory_facts(telegram_id: int, limit: int = 20):
    result = (
        supabase.table("user_memory")
        .select("fact")
        .eq("telegram_id", telegram_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return [
        item["fact"]
        for item in result.data or []
        if item.get("fact")
    ]


def get_user_memory(telegram_id: int):
    facts = get_user_memory_facts(telegram_id)

    if not facts:
        return ""

    return "\n".join([f"- {fact}" for fact in facts])


def build_user_memory_context(telegram_id: int):
    memory = get_user_memory(telegram_id)

    if not memory:
        memory = "Пока нет сохранённых фактов."

    return {
        "role": "system",
        "content": (
            "Долговременная память о пользователе:\n"
            f"{memory}\n\n"
            "Эти факты включают информацию, которую пользователь мог сохранить вручную через /remember "
            "или кнопку «Факты обо мне»: ограничения, аллергии, непереносимости, предпочтения, цели, "
            "режим питания, продукты, которые пользователь не ест, и личные рекомендации, которые он хочет учитывать. "
            "Обязательно учитывай их при анализе еды и персональных рекомендациях. "
            "Если сохранённый факт влияет на оценку блюда, ограничения, цели, аллергию, непереносимость, "
            "режим питания, сон, стресс или тренировки, адаптируй ответ под этот факт. "
            "Не советуй продукты и действия, которые конфликтуют с сохранёнными ограничениями пользователя. "
            "Упоминай ограничения только тогда, когда в блюде, тексте или на фото явно есть или вероятно "
            "указан в составе продукт, который пользователь сохранил как 'не ем', 'не переношу', "
            "'аллергия' или другой запрет/ограничение. Не хвали блюдо за отсутствие запрещённого продукта "
            "и не пиши 'нет X, это хорошо'. Если конфликт есть, коротко отметь, что в составе есть "
            "нежелательный для пользователя продукт/компонент, и предложи замену. Не называй такой "
            "продукт плюсом блюда для этого пользователя и не советуй добавлять его или похожие "
            "нежелательные продукты. "
            "Не перечисляй всю память без необходимости, но кратко упоминай релевантный факт, "
            "если он объясняет рекомендацию. "
            "Не начинай ответ с фраз о том, что информация не найдена в загруженных файлах, документах "
            "или базе знаний. Если точных данных в материалах нет, просто дай полезный ответ из общих "
            "знаний и персонального контекста пользователя."
        )
    }


def is_memory_save_request(text: str) -> bool:
    normalized = (text or "").lower().replace("ё", "е").strip()

    if not normalized:
        return False

    memory_request_markers = (
        "запомни, что",
        "запомни что",
        "запомни это",
        "запомни:",
        "добавь в память",
        "добавь в базу знаний",
        "сохрани в память",
        "сохрани как факт",
        "сохрани это как факт",
        "запиши в память",
        "это важно запомнить",
        "учти в будущем",
        "запомни на будущее",
    )

    return normalized.startswith(memory_request_markers)


async def prompt_memory_save_via_menu(message: types.Message):
    await message.answer(
        "Чтобы я действительно сохранил это в долгосрочную память, добавь факт через меню "
        f"«{MENU_MEMORY}» -> «Добавить факт».\n\n"
        "Тогда я буду стабильно учитывать его в следующих рекомендациях и анализе питания.",
        reply_markup=main_keyboard()
    )


def save_user_memory_fact(telegram_id: int, fact: str):
    fact = (fact or "").strip()

    if not fact:
        return "empty"

    existing = (
        supabase.table("user_memory")
        .select("fact")
        .eq("telegram_id", telegram_id)
        .eq("fact", fact)
        .execute()
    )

    if existing.data:
        return "duplicate"

    supabase.table("user_memory").insert({
        "telegram_id": telegram_id,
        "fact": fact
    }).execute()

    return "saved"


def delete_user_memory_fact(telegram_id: int, fact: str):
    fact = (fact or "").strip()

    if not fact:
        return "empty"

    existing = (
        supabase.table("user_memory")
        .select("fact")
        .eq("telegram_id", telegram_id)
        .eq("fact", fact)
        .limit(1)
        .execute()
    )

    if not existing.data:
        return "not_found"

    supabase.table("user_memory").delete().eq(
        "telegram_id",
        telegram_id
    ).eq("fact", fact).execute()

    return "deleted"


async def save_memory_from_text(message: types.Message, fact: str):
    telegram_id = message.from_user.id

    try:
        status = save_user_memory_fact(telegram_id, fact)
    except Exception as e:
        print("MANUAL MEMORY SAVE ERROR:", repr(e))
        await message.answer(
            "Не смог сохранить факт в память. Попробуй ещё раз.",
            reply_markup=main_keyboard()
        )
        return

    if status == "duplicate":
        await message.answer("Этот факт уже есть в моей памяти.", reply_markup=main_keyboard())
        return

    await message.answer(
        "Запомнил. Посмотреть сохранённое можно через кнопку «Факты обо мне» или /memory.",
        reply_markup=main_keyboard()
    )


async def delete_memory_from_text(message: types.Message, value: str):
    telegram_id = message.from_user.id
    value = (value or "").strip()

    try:
        if value.isdigit():
            facts = get_user_memory_facts(telegram_id)
            index = int(value)

            if index < 1 or index > len(facts):
                await message.answer(
                    "Не нашёл факт с таким номером. Проверь список через кнопку «Факты обо мне».",
                    reply_markup=main_keyboard()
                )
                return

            fact = facts[index - 1]
        else:
            fact = value

        status = delete_user_memory_fact(telegram_id, fact)
    except Exception as e:
        print("MANUAL MEMORY DELETE ERROR:", repr(e))
        await message.answer(
            "Не смог удалить факт из памяти. Попробуй ещё раз.",
            reply_markup=main_keyboard()
        )
        return

    if status == "not_found":
        await message.answer("Не нашёл такой факт в памяти.", reply_markup=main_keyboard())
        return

    await message.answer("Удалил факт из памяти.", reply_markup=main_keyboard())
