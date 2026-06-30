from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)


BOT_COMMANDS = [
    BotCommand(command="start", description="Запустить бота"),
    BotCommand(command="help", description="Что умеет бот"),
    BotCommand(command="recipes", description="Открыть книгу рецептов"),
    BotCommand(command="feedback", description="Написать обратную связь"),
    BotCommand(command="subscription", description="Статус подписки"),
    BotCommand(command="cancel_subscription", description="Отменить подписку"),
    BotCommand(command="memory", description="Показать сохранённые факты"),
    BotCommand(command="remember", description="Добавить факт в память"),
    BotCommand(command="forget", description="Удалить факт из памяти"),
]

MENU_RECIPES = "Книга рецептов"
MENU_MEMORY = "Факты обо мне"
MENU_FEEDBACK = "Обратная связь"
MENU_HELP = "Помощь"
MENU_CANCEL = "Отмена"


def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=MENU_RECIPES),
                KeyboardButton(text=MENU_HELP),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Опиши еду или выбери действие",
    )


def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=MENU_CANCEL),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Отправь значение или нажми Отмена",
    )


def hide_keyboard():
    return ReplyKeyboardRemove()


def help_actions_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Факты обо мне",
                    callback_data="memory:show"
                ),
                InlineKeyboardButton(
                    text="Обратная связь",
                    callback_data="feedback:start"
                ),
            ],
        ]
    )


def help_text():
    return (
        "Что я умею:\n\n"
        "📸 Анализировать еду по фото без осуждения и запретов\n"
        "🥗 Подсказывать, как улучшить конкретный приём пищи\n"
        "📦 Разбирать состав продуктов по фото упаковки\n"
        "🌍 Переводить составы с английского и других языков на русский\n"
        "📚 Показывать книгу рецептов по разделам\n"
        "👣 Помогать менять питание маленькими привычками\n"
        "🍔 Подсказывать, как снизить последствия менее полезной еды\n"
        "💡 Давать персональные рекомендации с учётом твоих целей и ограничений\n"
        "🧠 Запоминать факты о тебе: ограничения, аллергии, предпочтения, цели и режим\n\n"
        "💳 Подписка: статус — /subscription, отмена автосписания — /cancel_subscription\n\n"
        "✉️ Принимать обратную связь и сообщения в поддержку\n\n"
        "Добавь факты о себе, чтобы рекомендации учитывали твои нюансы.\n"
        "Можно просто написать, что ты съел, спросить, как улучшить блюдо, или отправить фото еды."
    )
