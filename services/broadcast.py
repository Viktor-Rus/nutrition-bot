import asyncio

from aiogram import types

from clients import bot, supabase
from services.support import is_support_chat
from state import BROADCAST_DRAFTS


DEFAULT_INACTIVE_START_BROADCAST_TEXT = (
    "Привет, {name}! Видел, что ты открыл MealAdvisor, но ещё ничего не отправлял.\n\n"
    "Можно начать совсем просто: пришли фото любого приёма пищи, перекуса "
    "или состава продукта с упаковки.\n\n"
    "Я не буду ругать и запрещать. Просто подскажу:\n"
    "• что уже нормально\n"
    "• что можно улучшить\n"
    "• какой маленький шаг сделать без жёстких диет\n\n"
    "Попробуй с последнего фото еды в телефоне 🙂"
)


def get_broadcast_recipients():
    recipients = []
    page_size = 1000
    start = 0

    while True:
        try:
            result = (
                supabase.table("users")
                .select("telegram_id, name, username, is_blocked")
                .range(start, start + page_size - 1)
                .execute()
            )
        except Exception as e:
            print("BROADCAST RECIPIENTS USERNAME FALLBACK:", repr(e))
            result = (
                supabase.table("users")
                .select("telegram_id, name")
                .range(start, start + page_size - 1)
                .execute()
            )

        rows = result.data or []

        for row in rows:
            if row.get("is_blocked") is True:
                continue

            telegram_id = row.get("telegram_id")

            if telegram_id:
                recipients.append({
                    "telegram_id": int(telegram_id),
                    "name": row.get("name") or "",
                    "username": row.get("username") or "",
                })

        if len(rows) < page_size:
            break

        start += page_size

    unique_recipients = {}

    for recipient in recipients:
        unique_recipients[recipient["telegram_id"]] = recipient

    return [
        unique_recipients[telegram_id]
        for telegram_id in sorted(unique_recipients)
    ]


def get_table_telegram_ids(table_name: str):
    telegram_ids = set()
    page_size = 1000
    start = 0

    while True:
        result = (
            supabase.table(table_name)
            .select("telegram_id")
            .range(start, start + page_size - 1)
            .execute()
        )

        rows = result.data or []

        for row in rows:
            telegram_id = row.get("telegram_id")

            if telegram_id:
                telegram_ids.add(int(telegram_id))

        if len(rows) < page_size:
            break

        start += page_size

    return telegram_ids


def get_inactive_start_recipients():
    recipients = get_broadcast_recipients()
    active_telegram_ids = (
        get_table_telegram_ids("messages")
        | get_table_telegram_ids("meals")
    )

    return [
        recipient
        for recipient in recipients
        if recipient["telegram_id"] not in active_telegram_ids
    ]


def format_recipient(recipient):
    name = recipient.get("name") or "Без имени"
    username = recipient.get("username")
    username_text = f"@{username}" if username else "username не указан"

    return f"{name} ({username_text}) — {recipient['telegram_id']}"


def render_broadcast_text(template: str, recipient):
    username = recipient.get("username")

    return template.format(
        name=recipient.get("name") or "друг",
        username=f"@{username}" if username else "",
        telegram_id=recipient["telegram_id"],
    )


def format_recipients_preview(recipients, limit: int = 10):
    lines = [
        f"- {format_recipient(recipient)}"
        for recipient in recipients[:limit]
    ]

    if len(recipients) > limit:
        lines.append(f"...и ещё {len(recipients) - limit}")

    return "\n".join(lines)


def format_delivery_report(delivered, failed, limit: int = 15):
    report_parts = []

    if delivered:
        delivered_lines = [
            f"- {format_recipient(recipient)}"
            for recipient in delivered[:limit]
        ]

        if len(delivered) > limit:
            delivered_lines.append(f"...и ещё {len(delivered) - limit}")

        report_parts.append("Отправлено:\n" + "\n".join(delivered_lines))

    if failed:
        failed_lines = [
            f"- {format_recipient(recipient)}"
            for recipient in failed[:limit]
        ]

        if len(failed) > limit:
            failed_lines.append(f"...и ещё {len(failed) - limit}")

        report_parts.append("Ошибки:\n" + "\n".join(failed_lines))

    return "\n\n".join(report_parts)


async def save_broadcast_draft(
    message: types.Message,
    broadcast_text: str,
    recipients,
    recipient_type: str,
    title: str = "Черновик рассылки создан.",
):
    if len(broadcast_text) > 3500:
        await message.answer("Сообщение слишком длинное. Сократи текст до 3500 символов.")
        return

    if not recipients:
        await message.answer("Не нашёл пользователей для этой рассылки.")
        return

    try:
        preview_text = render_broadcast_text(broadcast_text, recipients[0])
    except KeyError as e:
        await message.answer(
            f"Неизвестный плейсхолдер: {{{e.args[0]}}}\n\n"
            "Доступные плейсхолдеры: {name}, {username}, {telegram_id}"
        )
        return
    except ValueError:
        await message.answer(
            "Не смог разобрать плейсхолдеры в тексте.\n\n"
            "Если тебе нужны фигурные скобки как обычный текст, напиши их двойными: {{ и }}."
        )
        return

    BROADCAST_DRAFTS[str(message.chat.id)] = {
        "text": broadcast_text,
        "created_by": message.from_user.id,
        "recipient_type": recipient_type,
    }

    await message.answer(
        f"{title}\n\n"
        f"Получателей: {len(recipients)}\n\n"
        "Получатели:\n"
        f"{format_recipients_preview(recipients)}\n\n"
        "Доступные плейсхолдеры: {name}, {username}, {telegram_id}\n\n"
        f"Текст:\n{broadcast_text}\n\n"
        f"Пример для первого пользователя:\n{preview_text}\n\n"
        "Чтобы отправить, напиши /confirm_broadcast\n"
        "Чтобы отменить, напиши /cancel_broadcast"
    )


async def create_broadcast_draft(message: types.Message):
    if not is_support_chat(message.chat.id):
        await message.answer("Эта команда доступна только в чате поддержки.")
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Формат рассылки:\n\n"
            "/broadcast текст сообщения\n\n"
            "Например: /broadcast Добавили книгу рецептов в меню."
        )
        return

    broadcast_text = parts[1].strip()

    try:
        recipients = get_broadcast_recipients()
    except Exception as e:
        print("BROADCAST RECIPIENTS ERROR:", repr(e))
        await message.answer("Не смог получить список пользователей для рассылки.")
        return

    await save_broadcast_draft(
        message=message,
        broadcast_text=broadcast_text,
        recipients=recipients,
        recipient_type="all",
    )


async def create_inactive_start_broadcast_draft(message: types.Message):
    if not is_support_chat(message.chat.id):
        await message.answer("Эта команда доступна только в чате поддержки.")
        return

    parts = (message.text or "").split(maxsplit=1)
    broadcast_text = (
        parts[1].strip()
        if len(parts) > 1 and parts[1].strip()
        else DEFAULT_INACTIVE_START_BROADCAST_TEXT
    )

    try:
        recipients = get_inactive_start_recipients()
    except Exception as e:
        print("INACTIVE START BROADCAST RECIPIENTS ERROR:", repr(e))
        await message.answer("Не смог получить список пользователей без сообщений.")
        return

    await save_broadcast_draft(
        message=message,
        broadcast_text=broadcast_text,
        recipients=recipients,
        recipient_type="inactive_start",
        title="Черновик рассылки пользователям без сообщений создан.",
    )


async def confirm_broadcast(message: types.Message):
    if not is_support_chat(message.chat.id):
        await message.answer("Эта команда доступна только в чате поддержки.")
        return

    draft = BROADCAST_DRAFTS.pop(str(message.chat.id), None)

    if not draft:
        await message.answer(
            "Нет активного черновика рассылки.\n\n"
            "Сначала создай его командой /broadcast текст сообщения"
        )
        return

    broadcast_text = draft["text"]
    recipient_type = draft.get("recipient_type", "all")

    try:
        if recipient_type == "inactive_start":
            recipients = get_inactive_start_recipients()
        else:
            recipients = get_broadcast_recipients()
    except Exception as e:
        print("BROADCAST RECIPIENTS ERROR:", repr(e))
        await message.answer("Не смог получить список пользователей для рассылки.")
        return

    if not recipients:
        await message.answer("Не нашёл пользователей для этой рассылки.")
        return

    sent = 0
    failed = 0
    delivered_recipients = []
    failed_recipients = []

    progress_message = await message.answer(
        f"Начинаю рассылку для {len(recipients)} пользователей..."
    )

    for index, recipient in enumerate(recipients, start=1):
        try:
            personal_text = render_broadcast_text(broadcast_text, recipient)
            await bot.send_message(
                chat_id=recipient["telegram_id"],
                text=personal_text
            )
            sent += 1
            delivered_recipients.append(recipient)
        except KeyError as e:
            failed += 1
            failed_recipients.append(recipient)
            print("BROADCAST TEMPLATE ERROR:", recipient["telegram_id"], repr(e))
        except ValueError as e:
            failed += 1
            failed_recipients.append(recipient)
            print("BROADCAST TEMPLATE FORMAT ERROR:", recipient["telegram_id"], repr(e))
        except Exception as e:
            failed += 1
            failed_recipients.append(recipient)
            print("BROADCAST SEND ERROR:", recipient["telegram_id"], repr(e))

        if index % 25 == 0:
            await asyncio.sleep(1)
        else:
            await asyncio.sleep(0.05)

    await progress_message.edit_text(
        "Рассылка завершена.\n\n"
        f"Получателей: {len(recipients)}\n"
        f"Отправлено: {sent}\n"
        f"Ошибок: {failed}\n\n"
        f"{format_delivery_report(delivered_recipients, failed_recipients)}"
    )


async def cancel_broadcast(message: types.Message):
    if not is_support_chat(message.chat.id):
        await message.answer("Эта команда доступна только в чате поддержки.")
        return

    draft = BROADCAST_DRAFTS.pop(str(message.chat.id), None)

    if not draft:
        await message.answer("Нет активного черновика рассылки.")
        return

    await message.answer("Черновик рассылки отменён.")
