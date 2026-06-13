import os

from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_VECTOR_STORE_ID = os.getenv("OPENAI_VECTOR_STORE_ID")
SUPPORT_CHAT_ID = os.getenv("SUPPORT_CHAT_ID")
YOOKASSA_PROVIDER_TOKEN = os.getenv("YOOKASSA_PROVIDER_TOKEN")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
APP_BASE_URL = os.getenv("APP_BASE_URL", "").rstrip("/")
SUBSCRIPTION_CRON_SECRET = os.getenv("SUBSCRIPTION_CRON_SECRET")
PAYMENT_TITLE = os.getenv("PAYMENT_TITLE", "MealAdvisor Premium")
PAYMENT_DESCRIPTION = os.getenv(
    "PAYMENT_DESCRIPTION",
    "Доступ к расширенным возможностям MealAdvisor."
)
PAYMENT_LABEL = os.getenv("PAYMENT_LABEL", "MealAdvisor Premium")
PAYMENT_CURRENCY = os.getenv("PAYMENT_CURRENCY", "RUB")
PAYMENT_AMOUNT = int(os.getenv("PAYMENT_AMOUNT", "199000"))
PAYMENT_PROVIDER_DATA = os.getenv("PAYMENT_PROVIDER_DATA")
SUBSCRIPTION_TRIAL_DAYS = int(os.getenv("SUBSCRIPTION_TRIAL_DAYS", "7"))
SUBSCRIPTION_MONTHLY_AMOUNT = int(os.getenv("SUBSCRIPTION_MONTHLY_AMOUNT", "199000"))


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
