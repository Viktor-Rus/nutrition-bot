from aiogram import types

from clients import supabase


def build_user_profile(user: types.User):
    return {
        "telegram_id": user.id,
        "name": user.full_name,
        "username": user.username,
    }


def upsert_user_profile(user: types.User):
    profile = build_user_profile(user)

    try:
        supabase.table("users").upsert(profile).execute()
    except Exception as e:
        print("SUPABASE USER PROFILE ERROR:", repr(e))
        supabase.table("users").upsert({
            "telegram_id": profile["telegram_id"],
            "name": profile["name"],
        }).execute()


def maybe_upsert_private_user(message: types.Message):
    if not message.from_user or message.chat.type != "private":
        return

    try:
        upsert_user_profile(message.from_user)
    except Exception as e:
        print("SUPABASE USER ERROR:", repr(e))
