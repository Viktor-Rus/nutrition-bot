from aiogram.types import BotCommand, KeyboardButton, ReplyKeyboardMarkup


BOT_COMMANDS = [
    BotCommand(command="start", description="Запустить бота"),
    BotCommand(command="help", description="Что умеет бот"),
    BotCommand(command="recipes", description="Открыть книгу рецептов"),
    BotCommand(command="feedback", description="Написать обратную связь"),
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
                KeyboardButton(text=MENU_MEMORY),
            ],
            [
                KeyboardButton(text=MENU_FEEDBACK),
                KeyboardButton(text=MENU_HELP),
            ],
        ],
        resize_keyboard=True,
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


def help_text():
    return (
        "Что я умею:\n\n"
        "📸 Анализировать еду по фото\n"
        "🥗 Анализировать блюда и продукты по описанию\n"
        "📦 Разбирать состав продуктов по фото упаковки\n"
        "🌍 Переводить составы с английского и других языков на русский\n"
        "📚 Показывать книгу рецептов по разделам\n"
        "💡 Давать персональные рекомендации по питанию и привычкам\n"
        "🧠 Запоминать важные факты через /remember\n"
        "🗑 Удалять факты из памяти через /forget\n\n"
        "✉️ Принимать обратную связь через кнопку «Обратная связь»\n\n"
        "Можно просто написать, что ты съел, или отправить фото еды."
    )
