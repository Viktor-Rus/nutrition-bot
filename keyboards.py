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
                    text="Книга рецептов",
                    callback_data="recipes:home"
                ),
            ],
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
        "🍽 Анализ еды\n"
        "• Разбираю еду по фото или описанию\n"
        "• Оцениваю приём пищи без осуждения\n"
        "• Подсказываю, что можно улучшить\n\n"
        "📦 Состав продуктов\n"
        "• Читаю состав по фото упаковки\n"
        "• Перевожу составы на русский\n"
        "• Помогаю заметить нежелательные ингредиенты\n\n"
        "📚 Рецепты и привычки\n"
        "• Показываю книгу рецептов — /recipes\n"
        "• Даю идеи завтраков, обедов, ужинов и перекусов\n"
        "• Помогаю менять питание маленькими шагами\n\n"
        "🧠 Персонализация\n"
        "• Учитываю цели, ограничения, аллергии и предпочтения\n"
        "• Факты обо мне — /memory\n\n"
        "💳 Подписка\n"
        "• Статус подписки — /subscription\n"
        "• Отмена автосписания — /cancel_subscription\n\n"
        "✉️ Поддержка\n"
        "• Обратная связь — /feedback\n\n"
        "Можно просто написать, что ты съел, задать вопрос про питание или отправить фото еды."
    )
