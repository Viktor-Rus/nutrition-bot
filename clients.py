from aiogram import Bot, Dispatcher
from openai import OpenAI
from supabase import create_client

from config import BOT_TOKEN, OPENAI_API_KEY, SUPABASE_KEY, SUPABASE_URL


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

openai_client = OpenAI(api_key=OPENAI_API_KEY)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)
