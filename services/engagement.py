from datetime import datetime, timedelta, timezone

from clients import bot, supabase
from config import IS_PRODUCTION, START_REACTIVATION_DELAY_HOURS
from keyboards import main_keyboard
from services.broadcast import DEFAULT_INACTIVE_START_BROADCAST_TEXT, render_broadcast_text
from services.users import set_user_blocked


START_REACTIVATION_LIMIT = 50


def now_utc():
    return datetime.now(timezone.utc)


def iso_dt(value):
    if not value:
        return None

    return value.astimezone(timezone.utc).isoformat()


def is_telegram_blocked_error(error):
    return "bot was blocked by the user" in repr(error).lower()


def get_start_reactivation_candidates(limit=START_REACTIVATION_LIMIT):
    cutoff = now_utc() - timedelta(hours=START_REACTIVATION_DELAY_HOURS)

    try:
        result = (
            supabase.table("users")
            .select(
                "telegram_id, name, username, created_at, is_blocked, "
                "reactivation_checked_at, reactivation_sent_at"
            )
            .is_("reactivation_checked_at", "null")
            .lte("created_at", iso_dt(cutoff))
            .order("created_at")
            .limit(limit)
            .execute()
        )
    except Exception as e:
        print("START REACTIVATION CANDIDATES ERROR:", repr(e))
        return []

    return [
        row
        for row in (result.data or [])
        if row.get("telegram_id") and row.get("is_blocked") is not True
    ]


def user_has_any_rows(table_name, telegram_id):
    result = (
        supabase.table(table_name)
        .select("id")
        .eq("telegram_id", telegram_id)
        .limit(1)
        .execute()
    )

    return bool(result.data)


def has_user_interaction_after_start(telegram_id):
    return (
        user_has_any_rows("messages", telegram_id)
        or user_has_any_rows("meals", telegram_id)
    )


def mark_start_reactivation_checked(telegram_id, sent=False):
    checked_at = iso_dt(now_utc())
    payload = {
        "reactivation_checked_at": checked_at,
    }

    if sent:
        payload["reactivation_sent_at"] = checked_at

    try:
        supabase.table("users").update(payload).eq("telegram_id", telegram_id).execute()
    except Exception as e:
        print("START REACTIVATION MARK ERROR:", telegram_id, repr(e))


async def send_start_reactivation_messages(limit=START_REACTIVATION_LIMIT):
    if not IS_PRODUCTION:
        return {
            "ok": True,
            "skipped": "non_production",
            "due": 0,
            "sent": 0,
            "failed": 0,
            "already_active": 0,
        }

    candidates = get_start_reactivation_candidates(limit=limit)
    sent = 0
    failed = 0
    already_active = 0

    for user in candidates:
        telegram_id = int(user["telegram_id"])

        try:
            if has_user_interaction_after_start(telegram_id):
                already_active += 1
                mark_start_reactivation_checked(telegram_id, sent=False)
                continue

            await bot.send_message(
                chat_id=telegram_id,
                text=render_broadcast_text(
                    DEFAULT_INACTIVE_START_BROADCAST_TEXT,
                    {
                        "telegram_id": telegram_id,
                        "name": user.get("name") or "",
                        "username": user.get("username") or "",
                    },
                ),
                reply_markup=main_keyboard(),
            )
            mark_start_reactivation_checked(telegram_id, sent=True)
            sent += 1
        except Exception as e:
            failed += 1

            if is_telegram_blocked_error(e):
                set_user_blocked(telegram_id, True)
                mark_start_reactivation_checked(telegram_id, sent=False)

            print("START REACTIVATION SEND ERROR:", telegram_id, repr(e))

    return {
        "ok": True,
        "due": len(candidates),
        "sent": sent,
        "failed": failed,
        "already_active": already_active,
    }
