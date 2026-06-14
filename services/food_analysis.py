import base64

from aiogram import types

from clients import bot, openai_client, supabase
from config import BOT_ROLE, OPENAI_VECTOR_STORE_ID
from keyboards import main_keyboard
from services.memory import build_user_memory_context, get_chat_history
from services.nutrition_classifier import is_nutrition_related


FOOD_ANALYSIS_FORMAT_INSTRUCTION = (
    "Для анализа еды отвечай в коротком визуально лёгком формате: "
    "🍽️ Что это, ⚠️ Оценка, ✅ Что уже хорошо, 🔧 Как улучшить, "
    "👣 Маленький шаг, 💬 Без перфекционизма. "
    "Если приём пищи явно слабый для здоровья: много сахара, ультра-переработанная еда, "
    "кофе натощак, алкоголь, курение рядом с едой, отсутствие белка/клетчатки или сильная "
    "сахарная нагрузка — честно скажи, что такой вариант лучше не делать регулярным "
    "и по возможности исключить/заменить. Не преуменьшай вред и не выдумывай плюсы. "
    "В блоке '✅ Что уже хорошо' указывай только реальные плюсы; если их почти нет, "
    "напиши коротко: 'сильных сторон мало' и перейди к улучшениям. "
    "Критикуй не пользователя, а сам состав приёма пищи. "
    "Не считай калории и БЖУ, если пользователь прямо не просит. "
    "Не завершай шаблонным предложением продолжить."
)


GENERAL_NUTRITION_ADVICE_INSTRUCTION = (
    "Пользователь задаёт общий вопрос или просит совет по питанию, а не описывает "
    "конкретный съеденный приём пищи. Не используй формат анализа еды с блоками "
    "'🍽️ Что это', '⚠️ Оценка', '✅ Что уже хорошо'. "
    "Отвечай гибко по смыслу вопроса: дай 2-4 практичных варианта, коротко объясни, "
    "почему они подходят, и заверши одним простым следующим шагом. "
    "Если вопрос про быстрый завтрак, предложи варианты на 5-10 минут. "
    "Если вопрос про вредную/менее полезную еду, объясни, как снизить последствия "
    "до, во время и после без самобичевания. "
    "Не считай калории и БЖУ, если пользователь прямо не просит. "
    "Учитывай сохранённые факты о пользователе."
)


def is_meal_analysis_request(text: str) -> bool:
    normalized = text.lower().replace("ё", "е").strip()

    advice_markers = (
        "какой",
        "какую",
        "какие",
        "что приготовить",
        "что съесть",
        "что есть",
        "что можно",
        "как сделать",
        "как улучшить",
        "как снизить",
        "посоветуй",
        "подскажи",
        "подбери",
        "варианты",
        "пример",
        "полезный",
        "если не успеваю",
        "не успеваю",
    )
    meal_report_markers = (
        "я съел",
        "я съела",
        "я сьел",
        "я сьела",
        "я выпил",
        "я выпила",
        "сегодня съел",
        "сегодня съела",
        "сегодня сьел",
        "сегодня сьела",
        "сегодня выпил",
        "сегодня выпила",
        "съел ",
        "съела ",
        "сьел ",
        "сьела ",
        "выпил ",
        "выпила ",
        "поел",
        "поела",
        "мой завтрак",
        "мой обед",
        "мой ужин",
        "мой перекус",
        "на завтрак ел",
        "на завтрак съел",
        "на обед ел",
        "на обед съел",
        "на ужин ел",
        "на ужин съел",
        "планирую съесть",
        "планирую сьесть",
        "буду есть",
        "буду пить",
        "хочу съесть",
        "хочу сьесть",
        "хочу выпить",
    )

    if any(marker in normalized for marker in meal_report_markers):
        return True

    if normalized.endswith("?") or any(marker in normalized for marker in advice_markers):
        return False

    return False


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
                "content": FOOD_ANALYSIS_FORMAT_INSTRUCTION
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Проанализируй фото еды. "
                            "Ответь коротко, тепло и практически: что видишь, дай честную оценку, "
                            "назови реальные плюсы, если они есть, объясни, как улучшить приём пищи "
                            "и какой один маленький шаг сделать в следующий раз. "
                            "Не считай калории и БЖУ, если пользователь прямо не просит. "
                            "Не превращай ответ в лекцию. Если приём пищи явно слабый, "
                            "не смягчай оценку и не выдумывай пользу, но сохраняй уважительный тон. "
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

        is_analysis_request = is_meal_analysis_request(text)
        response_instruction = (
            FOOD_ANALYSIS_FORMAT_INSTRUCTION
            if is_analysis_request
            else GENERAL_NUTRITION_ADVICE_INSTRUCTION
        )

        context_input = [
            build_user_memory_context(telegram_id)
        ] + history + [
            {
                "role": "system",
                "content": response_instruction
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

        if is_analysis_request:
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
