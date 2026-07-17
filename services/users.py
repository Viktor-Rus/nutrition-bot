from aiogram import types

from clients import supabase


def build_user_profile(user: types.User):
    return {
        "telegram_id": user.id,
        "name": user.full_name,
        "username": user.username,
        "is_blocked": False,
    }


def upsert_user_profile(user: types.User):
    profile = build_user_profile(user)

    try:
        supabase.table("users").upsert(
            profile,
            on_conflict="telegram_id",
        ).execute()
    except Exception as e:
        print("SUPABASE USER PROFILE ERROR:", repr(e))
        supabase.table("users").upsert({
            "telegram_id": profile["telegram_id"],
            "name": profile["name"],
        }, on_conflict="telegram_id").execute()


def maybe_upsert_private_user(message: types.Message):
    if not message.from_user or message.chat.type != "private":
        return

    try:
        upsert_user_profile(message.from_user)
    except Exception as e:
        print("SUPABASE USER ERROR:", repr(e))


def set_user_blocked(telegram_id: int, is_blocked: bool):
    try:
        supabase.table("users").update({
            "is_blocked": is_blocked,
        }).eq("telegram_id", telegram_id).execute()
    except Exception as e:
        print("SUPABASE USER BLOCKED STATUS ERROR:", telegram_id, repr(e))
