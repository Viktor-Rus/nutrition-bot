import os

from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_VECTOR_STORE_ID = os.getenv("OPENAI_VECTOR_STORE_ID")
SUPPORT_CHAT_ID = os.getenv("SUPPORT_CHAT_ID")


def load_bot_role():
    try:
        with open("prompt.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return """
Ты — личный AI-нутрициолог и консультант по здоровому образу жизни.

Отвечай по структуре:
1️⃣ Анализ
2️⃣ Что хорошо
3️⃣ Что можно улучшить
4️⃣ Практический совет
5️⃣ Вопрос пользователю

Не ставь медицинские диагнозы.
Если информации недостаточно — задай уточняющий вопрос.
"""


BOT_ROLE = load_bot_role()
