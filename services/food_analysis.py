import base64

from aiogram import types

from clients import bot, openai_client, supabase
from config import BOT_ROLE, OPENAI_VECTOR_STORE_ID
from keyboards import main_keyboard
from services.memory import build_user_memory_context, get_chat_history
from services.nutrition_classifier import is_nutrition_related


async def analyze_food_photo(message: types.Message):
    telegram_id = message.from_user.id

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)

        image_base64 = base64.b64encode(file_bytes.read()).decode("utf-8")

        history = get_chat_history(telegram_id, limit=8)

        context_input = [
            build_user_memory_context(telegram_id)
        ] + history + [
            {
                "role": "system",
                "content": (
                    "Для анализа еды отвечай в коротком визуально лёгком формате: "
                    "🍽️ Что это, Коротко, ✅ Что уже хорошо, 🔧 Как сделать лучше, "
                    "👣 Маленький шаг, 💬 Без перфекционизма. "
                    "Не считай калории и БЖУ, если пользователь прямо не просит. "
                    "Не завершай шаблонным предложением продолжить."
                )
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Проанализируй фото еды. "
                            "Ответь коротко, тепло и практически: что видишь, что уже хорошо, "
                            "как мягко улучшить приём пищи и какой один маленький шаг сделать в следующий раз. "
                            "Не считай калории и БЖУ, если пользователь прямо не просит. "
                            "Не превращай ответ в лекцию и не оценивай еду как плохую. "
                            "Если на фото не еда — вежливо скажи, что анализируешь только питание и близкие темы."
                        )
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{image_base64}"
                    }
                ]
            }
        ]

        response = openai_client.responses.create(
            model="gpt-4.1-mini",
            instructions=BOT_ROLE,
            input=context_input,
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [
                        OPENAI_VECTOR_STORE_ID
                    ]
                }
            ]
        )

        answer = response.output_text

        supabase.table("messages").insert({
            "telegram_id": telegram_id,
            "role": "user",
            "content": "[Фото еды]"
        }).execute()

        supabase.table("messages").insert({
            "telegram_id": telegram_id,
            "role": "assistant",
            "content": answer
        }).execute()

        supabase.table("meals").insert({
            "telegram_id": telegram_id,
            "text": "[Фото еды]",
            "ai_comment": answer
        }).execute()

        await message.answer(answer, reply_markup=main_keyboard())

    except Exception as e:
        print("PHOTO ANALYSIS ERROR:", repr(e))
        await message.answer(
            "Не смог проанализировать фото. Попробуй отправить другое изображение или описать еду текстом.",
            reply_markup=main_keyboard()
        )


async def analyze_food_text(message: types.Message):
    telegram_id = message.from_user.id
    text = message.text

    if not text:
        await message.answer(
            "Пока я умею анализировать только текст и фото еды.",
            reply_markup=main_keyboard()
        )
        return

    try:
        history = get_chat_history(telegram_id, limit=12)
    except Exception as e:
        print("CHAT HISTORY ERROR:", repr(e))
        history = []

    if not is_nutrition_related(text, history=history):
        await message.answer(
            "Я специализируюсь только на вопросах питания, здоровья, сна, тренировок и образа жизни.",
            reply_markup=main_keyboard()
        )
        return

    try:
        supabase.table("messages").insert({
            "telegram_id": telegram_id,
            "role": "user",
            "content": text
        }).execute()

        context_input = [
            build_user_memory_context(telegram_id)
        ] + history + [
            {
                "role": "system",
                "content": (
                    "Для анализа еды отвечай в коротком визуально лёгком формате: "
                    "🍽️ Что это, Коротко, ✅ Что уже хорошо, 🔧 Как сделать лучше, "
                    "👣 Маленький шаг, 💬 Без перфекционизма. "
                    "Не считай калории и БЖУ, если пользователь прямо не просит. "
                    "Не завершай шаблонным предложением продолжить."
                )
            },
            {
                "role": "user",
                "content": text
            }
        ]

        response = openai_client.responses.create(
            model="gpt-4.1-mini",
            instructions=BOT_ROLE,
            input=context_input,
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [
                        OPENAI_VECTOR_STORE_ID
                    ]
                }
            ]
        )

        answer = response.output_text

        supabase.table("messages").insert({
            "telegram_id": telegram_id,
            "role": "assistant",
            "content": answer
        }).execute()

        supabase.table("meals").insert({
            "telegram_id": telegram_id,
            "text": text,
            "ai_comment": answer
        }).execute()

        await message.answer(answer, reply_markup=main_keyboard())

    except Exception as e:
        print("OPENAI ERROR:", repr(e))
        await message.answer(
            "Не смог сейчас проанализировать сообщение.",
            reply_markup=main_keyboard()
        )
