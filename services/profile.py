import re
from datetime import datetime, timezone

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from clients import supabase
from keyboards import cancel_keyboard, main_keyboard
from services.memory import (
    delete_user_memory_fact,
    get_user_memory_facts,
    save_user_memory_fact,
)
from state import PENDING_ACTIONS, PROFILE_DRAFTS


PROFILE_ACTION_AGE = "profile:age"
PROFILE_ACTION_BODY = "profile:body"
PROFILE_ACTION_GOAL_TEXT = "profile:goal_text"
PROFILE_ACTION_PREFERENCES = "profile:preferences"
PROFILE_ACTION_RESTRICTIONS = "profile:restrictions"
PROFILE_TEXT_ACTIONS = {
    PROFILE_ACTION_AGE,
    PROFILE_ACTION_BODY,
    PROFILE_ACTION_GOAL_TEXT,
    PROFILE_ACTION_PREFERENCES,
    PROFILE_ACTION_RESTRICTIONS,
}

PROFILE_START_CALLBACK = "profile:start"
PROFILE_GOAL_PREFIX = "profile:goal:"

GOALS = {
    "weight_loss": "снизить вес",
    "muscle_gain": "набрать мышечную массу",
    "energy": "больше энергии и лучшее самочувствие",
    "healthy_habits": "наладить питание без жёстких диет",
}


def normalize_text(text: str):
    return (text or "").lower().replace("ё", "е").strip()


def profile_setup_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎯 Настроить под себя",
                    callback_data=PROFILE_START_CALLBACK,
                ),
            ],
        ]
    )


def goal_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Снизить вес",
                    callback_data=f"{PROFILE_GOAL_PREFIX}weight_loss",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Набрать мышцы",
                    callback_data=f"{PROFILE_GOAL_PREFIX}muscle_gain",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Больше энергии",
                    callback_data=f"{PROFILE_GOAL_PREFIX}energy",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Наладить питание",
                    callback_data=f"{PROFILE_GOAL_PREFIX}healthy_habits",
                ),
            ],
        ]
    )


def parse_age(text: str):
    match = re.search(r"\d{1,3}", text or "")
    if not match:
        return None

    age = int(match.group())
    if 10 <= age <= 100:
        return age

    return None


def parse_height_weight(text: str):
    numbers = [
        float(value.replace(",", "."))
        for value in re.findall(r"\d+(?:[,.]\d+)?", text or "")
    ]
    height = None
    weight = None

    for value in numbers:
        if height is None and 120 <= value <= 230:
            height = round(value)
            continue

        if weight is None and 35 <= value <= 250:
            weight = round(value)

    if height and weight:
        return height, weight

    return None, None


def parse_profile_updates(text: str):
    normalized = normalize_text(text)
    updates = {}

    weight_match = re.search(
        r"(?:вес|вешу|похудел|похудела|набрал|набрала|теперь|сейчас|стал|стала)"
        r"[^\d]{0,30}(\d{2,3})(?:[,.]\d+)?\s*(?:кг|килограмм)",
        normalized,
    )
    if weight_match:
        weight = int(weight_match.group(1))
        if 35 <= weight <= 250:
            updates["weight"] = weight

    height_match = re.search(
        r"(?:рост|вырос|выросла|теперь|сейчас)"
        r"[^\d]{0,30}(\d{3})(?:[,.]\d+)?\s*(?:см|сантиметр)",
        normalized,
    )
    if height_match:
        height = int(height_match.group(1))
        if 120 <= height <= 230:
            updates["height"] = height

    age_match = re.search(
        r"(?:возраст|мне|исполнилось)"
        r"[^\d]{0,20}(\d{1,3})\s*(?:лет|год|года)?",
        normalized,
    )
    if age_match:
        age = int(age_match.group(1))
        if 10 <= age <= 100:
            updates["age"] = age

    return updates


def build_profile_memory_fact(profile: dict):
    def value_or_empty(key):
        value = profile.get(key)
        return value if value not in (None, "") else "не указано"

    return (
        "Профиль питания: "
        f"возраст {value_or_empty('age')}, "
        f"рост {value_or_empty('height')} см, "
        f"вес {value_or_empty('weight')} кг, "
        f"цель — {value_or_empty('goal')}, "
        f"предпочтения — {value_or_empty('diet_preferences')}, "
        f"ограничения — {value_or_empty('restrictions')}."
    )


def format_updated_profile_fields(updates: dict):
    labels = {
        "age": "Возраст",
        "height": "Рост",
        "weight": "Вес",
    }
    suffixes = {
        "age": "",
        "height": " см",
        "weight": " кг",
    }

    return "\n".join(
        f"{labels[key]}: {value}{suffixes[key]}"
        for key, value in updates.items()
        if key in labels
    )


async def maybe_update_profile_from_text(message: types.Message):
    updates = parse_profile_updates(message.text or "")
    if not updates:
        return False

    user_id = message.from_user.id
    update_data = {
        **updates,
        "profile_completed_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        supabase.table("users").update(update_data).eq(
            "telegram_id",
            user_id,
        ).execute()
    except Exception as e:
        print("PROFILE QUICK UPDATE WITH TIMESTAMP ERROR:", repr(e))
        try:
            supabase.table("users").update(updates).eq(
                "telegram_id",
                user_id,
            ).execute()
        except Exception as fallback_error:
            print("PROFILE QUICK UPDATE ERROR:", repr(fallback_error))
            await message.answer(
                "Понял, но не смог обновить профиль в базе. Попробуй через /profile.",
                reply_markup=main_keyboard(),
            )
            return True

    profile = get_user_profile(user_id) or {}
    replace_profile_memory_fact(user_id, build_profile_memory_fact(profile))

    await message.answer(
        "Обновил профиль ✅\n\n"
        f"{format_updated_profile_fields(updates)}\n\n"
        "Теперь буду учитывать это в анализе еды и рекомендациях.",
        reply_markup=main_keyboard(),
    )
    return True


def get_user_profile_context(telegram_id: int):
    row = get_user_profile(telegram_id)
    if not row:
        return ""

    lines = []

    if row.get("age"):
        lines.append(f"- Возраст: {row['age']}")
    if row.get("height"):
        lines.append(f"- Рост: {row['height']} см")
    if row.get("weight"):
        lines.append(f"- Вес: {row['weight']} кг")
    if row.get("goal"):
        lines.append(f"- Цель: {row['goal']}")
    if row.get("diet_preferences"):
        lines.append(f"- Предпочтения: {row['diet_preferences']}")
    if row.get("restrictions"):
        lines.append(f"- Ограничения: {row['restrictions']}")

    if not lines:
        return ""

    return "\n".join(lines)


def get_user_profile(telegram_id: int):
    try:
        result = (
            supabase.table("users")
            .select("age,height,weight,goal,diet_preferences,restrictions")
            .eq("telegram_id", telegram_id)
            .limit(1)
            .execute()
        )
    except Exception as e:
        print("USER PROFILE CONTEXT ERROR:", repr(e))
        return None

    if not result.data:
        return None

    return result.data[0] or {}


def format_user_profile_for_display(telegram_id: int):
    row = get_user_profile(telegram_id)
    if not row:
        return ""

    age = row.get("age")
    height = row.get("height")
    weight = row.get("weight")
    goal = row.get("goal")
    preferences = row.get("diet_preferences")
    restrictions = row.get("restrictions")

    if not any([age, height, weight, goal, preferences, restrictions]):
        return ""

    lines = ["🎯 Профиль питания"]

    if age:
        lines.append(f"Возраст: {age}")
    if height:
        lines.append(f"Рост: {height} см")
    if weight:
        lines.append(f"Вес: {weight} кг")
    if goal:
        lines.append(f"Цель: {goal}")
    if preferences:
        lines.append(f"Предпочтения: {preferences}")
    if restrictions:
        lines.append(f"Ограничения: {restrictions}")

    return "\n".join(lines)


async def request_profile_setup(message: types.Message, user_id: int):
    PROFILE_DRAFTS[user_id] = {}
    PENDING_ACTIONS[user_id] = PROFILE_ACTION_AGE

    await message.answer(
        "Давай настроим рекомендации под тебя 🎯\n\n"
        "Сколько тебе лет? Напиши просто число.",
        reply_markup=cancel_keyboard(),
    )


async def handle_profile_pending_message(
    message: types.Message,
    action: str,
    text: str,
):
    user_id = message.from_user.id
    draft = PROFILE_DRAFTS.setdefault(user_id, {})

    if action == PROFILE_ACTION_AGE:
        age = parse_age(text)
        if not age:
            await message.answer(
                "Не понял возраст. Напиши число от 10 до 100, например: 32.",
                reply_markup=cancel_keyboard(),
            )
            return

        draft["age"] = age
        PENDING_ACTIONS[user_id] = PROFILE_ACTION_BODY
        await message.answer(
            "Теперь напиши рост и вес одним сообщением.\n\n"
            "Например: 178 см, 76 кг",
            reply_markup=cancel_keyboard(),
        )
        return

    if action == PROFILE_ACTION_BODY:
        height, weight = parse_height_weight(text)
        if not height or not weight:
            await message.answer(
                "Не смог разобрать рост и вес. Напиши примерно так: 178 см, 76 кг.",
                reply_markup=cancel_keyboard(),
            )
            return

        draft["height"] = height
        draft["weight"] = weight
        PENDING_ACTIONS[user_id] = PROFILE_ACTION_GOAL_TEXT
        await message.answer(
            "Какая сейчас главная цель?",
            reply_markup=goal_keyboard(),
        )
        return

    if action == PROFILE_ACTION_GOAL_TEXT:
        goal = (text or "").strip()
        if len(goal) < 3:
            await message.answer(
                "Напиши цель чуть подробнее. Например: хочу набрать мышечную массу.",
                reply_markup=cancel_keyboard(),
            )
            return

        await ask_preferences(message, user_id, goal)
        return

    if action == PROFILE_ACTION_PREFERENCES:
        await ask_restrictions(message, user_id, text)
        return

    if action == PROFILE_ACTION_RESTRICTIONS:
        await complete_profile(message, user_id, text)


async def ask_preferences(message: types.Message, user_id: int, goal: str):
    PROFILE_DRAFTS.setdefault(user_id, {})["goal"] = goal
    PENDING_ACTIONS[user_id] = PROFILE_ACTION_PREFERENCES

    await message.answer(
        "Какие продукты или формат питания тебе ближе?\n\n"
        "Например: люблю рыбу и творог, ближе растительный белок, хочу простые блюда на 20 минут.\n"
        "Если особых предпочтений нет, напиши: нет.",
        reply_markup=cancel_keyboard(),
    )


async def ask_restrictions(message: types.Message, user_id: int, preferences_text: str):
    preferences = (preferences_text or "").strip()
    if preferences.lower().replace("ё", "е") in {"нет", "нету", "без предпочтений"}:
        preferences = "нет явных предпочтений"

    PROFILE_DRAFTS.setdefault(user_id, {})["diet_preferences"] = preferences
    PENDING_ACTIONS[user_id] = PROFILE_ACTION_RESTRICTIONS

    await message.answer(
        "Есть продукты, которые ты не ешь, аллергии или непереносимости?\n\n"
        "Например: не ем морковь, не переношу молоко, аллергия на арахис.\n"
        "Если ограничений нет, так и напиши: нет.",
        reply_markup=cancel_keyboard(),
    )


async def handle_profile_goal_callback(callback: types.CallbackQuery):
    goal_key = (callback.data or "").removeprefix(PROFILE_GOAL_PREFIX)
    goal = GOALS.get(goal_key)

    if not goal:
        await callback.answer("Не понял цель")
        return

    await callback.answer()
    await ask_preferences(callback.message, callback.from_user.id, goal)


def replace_profile_memory_fact(user_id: int, fact: str):
    try:
        existing_facts = get_user_memory_facts(user_id, limit=50)
        for existing_fact in existing_facts:
            if existing_fact.startswith("Профиль питания:"):
                delete_user_memory_fact(user_id, existing_fact)
        save_user_memory_fact(user_id, fact)
    except Exception as e:
        print("PROFILE MEMORY SAVE ERROR:", repr(e))


async def complete_profile(message: types.Message, user_id: int, restrictions_text: str):
    draft = PROFILE_DRAFTS.pop(user_id, {})
    PENDING_ACTIONS.pop(user_id, None)

    restrictions = (restrictions_text or "").strip()
    if restrictions.lower().replace("ё", "е") in {"нет", "нету", "без ограничений"}:
        restrictions = "нет явных ограничений"

    profile_data = {
        "age": draft.get("age"),
        "height": draft.get("height"),
        "weight": draft.get("weight"),
        "goal": draft.get("goal"),
        "diet_preferences": draft.get("diet_preferences"),
        "restrictions": restrictions,
        "profile_completed_at": datetime.now(timezone.utc).isoformat(),
    }

    update_data = {
        key: value
        for key, value in profile_data.items()
        if value is not None
    }

    try:
        supabase.table("users").update(update_data).eq(
            "telegram_id",
            user_id,
        ).execute()
    except Exception as e:
        print("PROFILE USER SAVE ERROR:", repr(e))

    memory_fact = (
        build_profile_memory_fact({
            "age": draft.get("age"),
            "height": draft.get("height"),
            "weight": draft.get("weight"),
            "goal": draft.get("goal"),
            "diet_preferences": draft.get("diet_preferences"),
            "restrictions": restrictions,
        })
    )
    replace_profile_memory_fact(user_id, memory_fact)

    await message.answer(
        "Готово, настроил профиль 🎯\n\n"
        "Теперь при анализе еды, рецептах и советах я буду учитывать цель, рост, вес "
        "и ограничения. Можно сразу прислать фото еды или написать вопрос про питание.",
        reply_markup=main_keyboard(),
    )
