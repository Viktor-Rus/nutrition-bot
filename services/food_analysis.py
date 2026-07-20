import base64
import re

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from clients import bot, openai_client, supabase
from config import BOT_ROLE, OPENAI_VECTOR_STORE_ID
from keyboards import hide_keyboard
from services.memory import (
    build_user_memory_context,
    get_chat_history,
    is_memory_save_request,
    prompt_memory_save_via_menu,
    save_user_memory_fact,
)
from services.nutrition_classifier import is_nutrition_related


FOOD_ACTION_IMPROVE_TOMORROW = "food_action:improve_tomorrow"
FOOD_ACTION_REPLACEMENT = "food_action:replacement"
FOOD_ACTION_SAVE_HABIT = "food_action:save_habit"


def food_analysis_actions_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Как улучшить завтра?",
                    callback_data=FOOD_ACTION_IMPROVE_TOMORROW,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Подобрать замену",
                    callback_data=FOOD_ACTION_REPLACEMENT,
                ),
                InlineKeyboardButton(
                    text="Сохранить как привычку",
                    callback_data=FOOD_ACTION_SAVE_HABIT,
                ),
            ],
        ]
    )


FOOD_ANALYSIS_FORMAT_INSTRUCTION = (
    "Для анализа еды отвечай в коротком визуально лёгком формате: "
    "🍽️ Что это, ⚠️ Оценка, ✅ Что уже хорошо, 🔧 Как улучшить, "
    "👣 Маленький шаг, 💬 Без перфекционизма. "
    "Этот шаблон не нужно заполнять механически: если какой-то блок звучит искусственно "
    "или не добавляет пользы, сократи его или пропусти. Пиши на 'ты', живо и по-человечески, "
    "как спокойный нутрициолог в переписке, а не как анкета. "
    "Если еда выглядит нормальной, сбалансированной или без очевидных проблем, не растягивай "
    "ответ на полный шаблон. Дай короткую живую оценку в 2-3 небольших блока: что это, почему "
    "всё в порядке, и нужен ли маленький шаг. Можно писать прямо: 'Нормальный вариант, тут "
    "главное не усложнять' или 'выглядит ок, улучшения не обязательны'. "
    "Полный разбор с несколькими блоками нужен только если есть явный конфликт, слабое место, "
    "запрос на подробный анализ или пользователь просит улучшения. "
    "Меняй формулировки от ответа к ответу, чтобы не звучать одинаково. "
    "Если приём пищи явно слабый для здоровья: много сахара, ультра-переработанная еда, "
    "кофе натощак, алкоголь, курение рядом с едой, отсутствие белка/клетчатки или сильная "
    "сахарная нагрузка — честно скажи, что такой вариант лучше не делать регулярным "
    "и по возможности исключить/заменить. Не преуменьшай вред и не выдумывай плюсы. "
    "В блоке '✅ Что уже хорошо' указывай только реальные плюсы; если их почти нет, "
    "лучше пропусти блок или напиши естественно: 'из плюсов — ...', если хотя бы один плюс есть. "
    "Не используй сухую фразу 'сильных сторон мало'. "
    "В блоке '🔧 Как улучшить' не предлагай изменения только ради заполнения шаблона. "
    "Давай 1-3 конкретных улучшения под ситуацию: не просто 'добавь овощи', а какие именно "
    "варианты подойдут к этому блюду: салат, зелень, огурцы, тушёные овощи, вода, чай, "
    "безалкогольный напиток или другая уместная замена. "
    "Если приём пищи уже выглядит удачно и без очевидных слабых мест, так и скажи: "
    "'здесь улучшения не обязательны' или 'существенно улучшать ничего не нужно'. "
    "Не считай любой жареный, картофельный, зерновой, молочный или ресторанный элемент "
    "автоматически проблемным. Не называй еду 'жирной', 'калорийной', 'тяжёлой' или "
    "'менее полезной' только по общему впечатлению или по типичному сценарию блюда. "
    "Не додумывай детали, которых нет в тексте или на фото: количество масла, способ жарки, "
    "состав соуса, жирность продукта, размер порции, наличие сахара или точный рецепт. "
    "Например, если пользователь просто написал 'йогурт', не делай вывод, что там был "
    "добавленный сахар, ароматизаторы, загустители или сладкие наполнители, пока он сам этого "
    "не сказал или этого явно не видно. "
    "Если улучшение зависит от неизвестной детали, сначала коротко обозначь неопределённость "
    "и при необходимости задай один уточняющий вопрос. "
    "Не используй орехи и семена как универсальный совет по умолчанию. Предлагай их только если "
    "это действительно уместно по блюду и решает конкретную проблему: мало полезных жиров, "
    "мало текстуры, низкая сытость или пользователь сам просит идеи добавок. Для удачного "
    "сбалансированного блюда лучше написать, что улучшения не обязательны. Для десертов и сладких "
    "перекусов чаще предлагай уменьшить регулярность/порцию, выбрать менее сладкий вариант или "
    "добавить нормальный белковый приём пищи рядом, а не автоматически добавлять орехи/семена. "
    "Не повторяй один и тот же совет про орехи/семена в каждом ответе. "
    "Перед оценкой сверь блюдо с долговременной памятью пользователя, но упоминай сохранённые "
    "ограничения только если в блюде явно есть или вероятно указан в составе продукт, который "
    "пользователь не ест, не переносит или отметил как ограничение. Не хвали блюдо за отсутствие "
    "запрещённого продукта и не пиши 'нет X, это хорошо'. Если конфликт есть, коротко скажи: "
    "в составе есть нежелательный для пользователя продукт/компонент, и предложи замену. "
    "Не называй этот продукт плюсом и не советуй увеличивать его количество. "
    "Если в памяти пользователя есть непереносимость или запрет, а продукт/алкоголь присутствует "
    "в блюде, называй это главным конфликтом с его ограничением и предлагай понятную замену. "
    "Блок '👣 Маленький шаг' тоже не обязателен любой ценой: если улучшение не требуется, "
    "можно честно написать, что маленький шаг здесь не нужен и приём пищи уже ок. "
    "Не используй Markdown-разметку: не пиши **жирный текст**, ### заголовки и списки через дефис. "
    "Для визуального оформления используй эмодзи + короткую строку-заголовок и пункты через символ •. "
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
    "Если вопрос простой, отвечай коротко и разговорно, без ощущения лекции. "
    "Не повторяй одну и ту же структуру в каждом ответе; выбирай форму под ситуацию. "
    "Если вопрос про быстрый завтрак, предложи варианты на 5-10 минут. "
    "Если вопрос про вредную/менее полезную еду, объясни, как снизить последствия "
    "до, во время и после без самобичевания. "
    "Оформляй варианты без Markdown-разметки: не используй **жирный текст**, ### заголовки "
    "и списки через дефис. Лучше: эмодзи + короткий заголовок на отдельной строке, затем "
    "1-2 предложения; для списков используй символ •. "
    "Не считай калории и БЖУ, если пользователь прямо не просит. "
    "Учитывай сохранённые факты о пользователе."
)


CONTINUE_ASSISTANT_OFFER_INSTRUCTION = (
    "Пользователь коротко согласился на твоё предыдущее предложение: например 'помоги', "
    "'давай', 'подбери', 'расскажи', 'составь'. Не спрашивай заново, с чем нужна помощь. "
    "Посмотри на последние сообщения и продолжи именно тот сценарий, который ты сам предложил: "
    "если предлагал составить рацион — составь примерный рацион; если предлагал подобрать блюда — "
    "подбери конкретные блюда; если предлагал рецепты — дай варианты рецептов. "
    "Если данных мало, сделай разумный стартовый вариант и в конце задай максимум 1-2 уточняющих "
    "вопроса для точной настройки. Учитывай сохранённые факты пользователя и не советуй то, что "
    "конфликтует с его ограничениями. Пиши конкретно, на 'ты', без фразы 'расскажи, с чем нужна помощь'."
)


CAPABILITY_QUESTION_INSTRUCTION = (
    "Пользователь спрашивает, правда ли ты можешь помочь, поможешь ли ты ему, "
    "чем ты полезен или сомневается в твоей пользе. Ответь живо, тепло и уверенно. "
    "Скажи прямо: да, я могу помочь в рамках питания, привычек и образа жизни. "
    "Назови конкретные направления: мягко скорректировать рацион, улучшить самочувствие "
    "после еды, снизить тягу к сладкому и перееданию, подобрать более удачные варианты "
    "блюд, наладить режим, энергию, сон и маленькие реалистичные шаги. "
    "Не обещай лечения, диагнозов или гарантированного результата. "
    "Не используй сухую фразу 'я специализируюсь только...'. "
    "Ответ должен звучать как нормальная человеческая поддержка, 3-6 предложений. "
    "В конце предложи начать с одного простого шага: пусть пользователь напишет, "
    "что ел сегодня, что хочет улучшить или что сейчас больше всего мешает."
)


MEAL_FOLLOW_UP_INSTRUCTION = (
    "Пользователь продолжает разговор о недавно обсуждённой еде или описывает "
    "самочувствие после неё. Отвечай как нутрициолог, который помнит предыдущий "
    "контекст и ведёт одну непрерывную консультацию. Не говори, что ты "
    "специализируешься только на питании, потому что вопрос уже относится к еде "
    "и реакции на неё. Сначала коротко признай ощущение пользователя без драматизации. "
    "Затем дай 2-4 вероятные пищевые причины по контексту, что можно сделать сейчас, "
    "что изменить в следующий раз и когда стоит насторожиться, если симптомы повторяются "
    "или усиливаются. Не ставь диагнозов. Не используй жёсткий шаблон анализа с блоками. "
    "Если пользователь просто делится ощущением, не требуй уточнений без необходимости: "
    "сначала дай полезную практическую поддержку. Пиши как живой эксперт, а не как "
    "анкета или инструкция. Не повторяй заново весь прошлый анализ блюда. Не начинай "
    "с общих фраз вроде 'это может быть связано с разными факторами' без конкретики. "
    "Лучше сразу свяжи ощущение с обсуждавшейся едой простым языком: например, объём, "
    "жирность, сочетание теста и соуса, скорость еды, индивидуальная реакция ЖКТ. "
    "Строй ответ естественно: 1) короткое человеческое признание ощущения, 2) вероятное "
    "объяснение по текущему контексту, 3) что сделать сейчас, 4) что изменить в следующий раз. "
    "Избегай канцелярита, сухих заголовков и повторяющихся формулировок. "
    "Пусть ответ звучит как продолжение диалога, а не как новый шаблон. "
    "Не додумывай состав продукта, если пользователь его не описал. Если он сказал только "
    "'йогурт', 'паста', 'пельмени' или другое общее название, не делай вид, что знаешь про "
    "добавленный сахар, соусы, количество масла, жирность, наполнители или способ приготовления. "
    "В таких случаях либо говори осторожно: 'если йогурт был сладкий/с добавками, это тоже могло "
    "повлиять', либо задай один короткий уточняющий вопрос, только если без него совет будет "
    "слишком неточным. "
    "Если данных мало, не переходи сразу к совету 'уменьшить сахар', 'снизить масло' или "
    "'убрать соус' как к уже установленному факту."
)


def is_capability_question(text: str) -> bool:
    normalized = text.lower().replace("ё", "е")
    normalized_compact = re.sub(r"\s+", "", normalized)

    markers = (
        "ты поможешь",
        "поможешь мне",
        "поможешь или нет",
        "реально поможешь",
        "действительно поможешь",
        "правда поможешь",
        "можешь помочь",
        "сможешь помочь",
        "ты можешь помочь",
        "чем ты поможешь",
        "как ты поможешь",
        "от тебя есть польза",
        "какая от тебя польза",
        "зачем ты нужен",
        "что ты умеешь",
        "чем можешь помочь",
    )
    compact_markers = (
        "реальнопоможешь",
        "такипоможешьилинет",
        "такпоможешьилинет",
    )

    return (
        any(marker in normalized for marker in markers)
        or any(marker in normalized_compact for marker in compact_markers)
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
    meal_report_patterns = (
        r"^(ел|ела|пил|пила)\b",
        r"^(съел|съела|сьел|сьела|выпил|выпила)\b",
        r"^на\s+(завтрак|обед|ужин|перекус)\s+(ел|ела|съел|съела)\b",
    )

    if any(marker in normalized for marker in meal_report_markers):
        return True

    if any(re.search(pattern, normalized) for pattern in meal_report_patterns):
        return True

    if normalized.endswith("?") or any(marker in normalized for marker in advice_markers):
        return False

    return False


def has_recent_food_context(history) -> bool:
    recent_messages = history[-6:] if history else []
    if not recent_messages:
        return False

    recent_text = " ".join(
        str(item.get("content", ""))
        for item in recent_messages
    ).lower().replace("ё", "е")

    food_context_markers = (
        "что это",
        "оценка",
        "что уже хорошо",
        "как улучшить",
        "маленький шаг",
        "без перфекционизма",
        "прием пищи",
        "состав",
        "завтрак",
        "обед",
        "ужин",
        "перекус",
        "блюдо",
        "продукт",
        "пельмен",
        "котлет",
        "салат",
        "суп",
        "хлеб",
        "каша",
        "омлет",
    )

    return any(marker in recent_text for marker in food_context_markers)


def has_recent_symptom_context(history) -> bool:
    recent_messages = history[-6:] if history else []
    if not recent_messages:
        return False

    recent_text = " ".join(
        str(item.get("content", ""))
        for item in recent_messages
    ).lower().replace("ё", "е")

    symptom_context_markers = (
        "тяжест",
        "вздут",
        "изжог",
        "тошнот",
        "дискомфорт",
        "урчит",
        "бурлит",
        "газ",
        "переел",
        "переполн",
        "тяжело",
        "сонлив",
        "слабост",
        "болит живот",
        "что можно сделать сейчас",
        "что делать сейчас",
        "что лучше сделать сейчас",
    )

    return any(marker in recent_text for marker in symptom_context_markers)


def has_recent_assistant_offer_context(history) -> bool:
    recent_messages = history[-6:] if history else []
    if not recent_messages:
        return False

    recent_assistant_text = " ".join(
        str(item.get("content", ""))
        for item in recent_messages
        if item.get("role") == "assistant"
    ).lower().replace("ё", "е")

    assistant_offer_markers = (
        "могу помочь",
        "могу подсказать",
        "могу помочь с советами",
        "если нужно, могу помочь",
        "если хочешь, могу помочь",
        "составить примерный рацион",
        "составить рацион",
        "подобрать конкретные блюда",
        "подобрать блюда",
        "подобрать варианты",
        "помочь с рецептами",
        "план набора мышечной массы",
        "по выбору",
        "по приготовлению",
        "что сделать сейчас",
        "что изменить в следующий раз",
    )

    return any(marker in recent_assistant_text for marker in assistant_offer_markers)


def is_assistant_offer_acceptance(text: str, history) -> bool:
    normalized = text.lower().replace("ё", "е").strip()
    compact_text = normalized.strip(" .!?")

    acceptance_replies = (
        "помоги",
        "помочь",
        "давай",
        "да",
        "ок",
        "окей",
        "хорошо",
        "подскажи",
        "подбери",
        "составь",
        "расскажи",
        "хочу",
        "нужно",
    )

    return (
        compact_text in acceptance_replies
        and has_recent_assistant_offer_context(history)
    )


def normalize_good_meal_analysis(answer: str) -> str:
    answer = normalize_telegram_markdown(answer)
    normalized = answer.lower().replace("ё", "е")

    positive_assessment_markers = (
        "очень сбалансирован",
        "хороший и сбалансированный",
        "сбалансированный и питательный",
        "хорошее сочетание белков",
        "выглядит вполне рабочим вариантом",
    )
    strong_negative_markers = (
        "лучше не делать регулярным",
        "слабый прием пищи",
        "слабый приём пищи",
        "много сахара",
        "ультра-переработ",
        "алкогол",
        "кофе натощак",
    )
    speculative_markers = (
        "более плотный элемент",
        "плотный элемент",
        "сделать прием пищи легче",
        "сделать приём пищи легче",
        "можно чуть изменить",
        "можно слегка облегчить",
        "уменьшить количество масла",
        "заменить часть картофеля",
        "добавить чуть больше разноцветных овощей",
        "для микронутриентов",
        "если возможно",
    )

    if not any(marker in normalized for marker in positive_assessment_markers):
        return answer

    if any(marker in normalized for marker in strong_negative_markers):
        return answer

    if not any(marker in normalized for marker in speculative_markers):
        return answer

    answer = re.sub(
        r"(⚠️ Оценка\n)(.*?)(\n✅ Что уже хорошо)",
        (
            r"\1"
            "Это очень сбалансированный и питательный приём пищи с белком, "
            "полезными жирами и овощами. По фото здесь нет явных слабых мест, "
            "которые нужно обязательно корректировать."
            r"\3"
        ),
        answer,
        count=1,
        flags=re.S,
    )

    answer = re.sub(
        r"(🔧 Как улучшить\n)(.*?)(\n👣 Маленький шаг)",
        (
            r"\1"
            "• здесь улучшения не обязательны\n"
            "• если ты хорошо себя чувствуешь после такого приёма пищи, его можно спокойно оставлять как есть"
            r"\3"
        ),
        answer,
        count=1,
        flags=re.S,
    )

    answer = re.sub(
        r"(👣 Маленький шаг\n)(.*?)(\n💬 Без перфекционизма)",
        (
            r"\1"
            "Маленький шаг здесь не обязателен: это уже хороший, собранный приём пищи."
            r"\3"
        ),
        answer,
        count=1,
        flags=re.S,
    )

    answer = re.sub(
        r"(💬 Без перфекционизма\n)(.*)$",
        (
            r"\1"
            "Не каждый хороший приём пищи нужно улучшать. Если такой вариант тебе подходит по самочувствию и насыщению, это уже удачный выбор."
        ),
        answer,
        count=1,
        flags=re.S,
    )

    return answer


def normalize_telegram_markdown(answer: str) -> str:
    if not answer:
        return answer

    answer = re.sub(r"\*\*(.+?)\*\*", r"\1", answer)
    answer = re.sub(r"__(.+?)__", r"\1", answer)

    lines = []
    for line in answer.splitlines():
        stripped = line.strip()

        heading_match = re.match(r"^#{1,6}\s+(.+)$", stripped)
        if heading_match:
            lines.append(f"🔹 {heading_match.group(1).strip()}")
            continue

        bullet_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet_match:
            lines.append(f"• {bullet_match.group(1).strip()}")
            continue

        lines.append(line)

    return "\n".join(lines)


def is_meal_follow_up_request(text: str, history) -> bool:
    normalized = text.lower().replace("ё", "е").strip()
    compact_text = normalized.strip(" .!?")
    has_food_context = has_recent_food_context(history)
    has_symptom_context = has_recent_symptom_context(history)
    has_assistant_offer_context = has_recent_assistant_offer_context(history)

    symptom_markers = (
        "тяжест",
        "вздут",
        "изжог",
        "тошнот",
        "дискомфорт",
        "урчит",
        "бурлит",
        "газ",
        "переел",
        "переполн",
        "тяжело",
        "тяжко",
        "сонлив",
        "слабост",
        "плохо",
        "нехорошо",
        "болит живот",
        "чувствую",
        "ощущаю",
        "после еды",
        "после такого",
        "после этого",
        "от этого",
        "от такого",
    )

    if not has_food_context and not has_symptom_context:
        return False

    if any(marker in normalized for marker in symptom_markers):
        return True

    simple_follow_up_replies = (
        "помоги",
        "помочь",
        "давай",
        "подскажи",
        "расскажи",
        "что посоветуешь",
        "и что теперь",
        "дальше",
    )

    if (
        compact_text in simple_follow_up_replies
        and has_food_context
        and has_assistant_offer_context
    ):
        return True

    short_follow_up_markers = (
        "это нормально",
        "почему так",
        "помоги",
        "что делать",
        "что делать сейчас",
        "что мне лучше сделать сейчас",
        "что лучше сделать сейчас",
        "что сейчас сделать",
        "как быть",
        "что лучше сейчас",
        "что можно сейчас",
        "как помочь",
        "как помочь себе",
        "как облегчить",
        "что выпить",
        "что съесть потом",
        "что лучше дальше",
        "из за чего",
        "из-за чего",
        "что это значит",
        "что это может значить",
        "что это может быть",
        "о чем это говорит",
        "о чём это говорит",
    )

    if (
        len(normalized) <= 160
        and (has_food_context or has_symptom_context)
        and any(
        marker in normalized for marker in short_follow_up_markers
        )
    ):
        return True

    immediate_action_markers = (
        "сейчас",
        "прямо сейчас",
        "что делать",
        "как быть",
        "как помочь",
        "как облегчить",
        "что выпить",
        "что это значит",
        "что это может значить",
        "что это может быть",
    )

    return (
        len(normalized) <= 120
        and has_symptom_context
        and any(marker in normalized for marker in immediate_action_markers)
    )


def get_latest_meal_thread(history):
    if not history:
        return []

    last_meal_index = None

    for index in range(len(history) - 1, -1, -1):
        item = history[index]
        if item.get("role") != "user":
            continue

        content = str(item.get("content", "")).strip()
        if content == "[Фото еды]" or (content and is_meal_analysis_request(content)):
            last_meal_index = index
            break

    if last_meal_index is None:
        return history[-6:]

    return history[last_meal_index:]


def build_follow_up_focus_context(history):
    meal_thread = get_latest_meal_thread(history)

    latest_meal_text = ""
    for item in meal_thread:
        if item.get("role") != "user":
            continue

        content = str(item.get("content", "")).strip()
        if content == "[Фото еды]":
            latest_meal_text = "последний обсуждавшийся приём пищи был отправлен фото"
            break

        if content and is_meal_analysis_request(content):
            latest_meal_text = content
            break

    focus_parts = [
        "Для текущего follow-up ориентируйся прежде всего на последний обсуждавшийся приём пищи, а не на более старые из истории.",
        "Если в истории есть более ранние блюда или старые жалобы, не связывай текущий вопрос с ними, если пользователь явно не возвращается именно к ним."
    ]

    if latest_meal_text:
        focus_parts.append(f"Последний релевантный приём пищи: {latest_meal_text}")

    return {
        "role": "system",
        "content": " ".join(focus_parts)
    }, meal_thread


def food_action_prompt(action: str):
    if action == FOOD_ACTION_IMPROVE_TOMORROW:
        return (
            "Пользователь нажал кнопку 'Как улучшить завтра?'. "
            "На основе последнего анализа еды предложи 2-3 очень конкретных и реалистичных "
            "способа улучшить похожий приём пищи завтра. Не ругай пользователя, не повторяй "
            "весь прошлый анализ. Пиши коротко, как личный помощник: что оставить, что чуть "
            "добавить или заменить. Если блюдо уже было хорошим, скажи, что можно оставить "
            "почти так же и предложи один необязательный маленький штрих."
        )

    if action == FOOD_ACTION_REPLACEMENT:
        return (
            "Пользователь нажал кнопку 'Подобрать замену'. "
            "На основе последнего анализа еды предложи 3 понятные замены или альтернативы: "
            "одну максимально простую, одну более сытную/сбалансированную, одну удобную на каждый день. "
            "Учитывай цель, ограничения и предпочтения пользователя из памяти. Не предлагай продукты, "
            "которые конфликтуют с его ограничениями. Пиши коротко и практически."
        )

    if action == FOOD_ACTION_SAVE_HABIT:
        return (
            "Пользователь нажал кнопку 'Сохранить как привычку'. "
            "На основе последнего анализа еды сформулируй одну короткую полезную привычку от первого лица, "
            "которую стоит сохранить в память пользователя. Верни только саму привычку, без заголовков, "
            "без пояснений и без кавычек. Пример: 'Добавлять источник белка к завтраку'."
        )

    return ""


def food_action_label(action: str):
    labels = {
        FOOD_ACTION_IMPROVE_TOMORROW: "Как улучшить завтра?",
        FOOD_ACTION_REPLACEMENT: "Подобрать замену",
        FOOD_ACTION_SAVE_HABIT: "Сохранить как привычку",
    }
    return labels.get(action, "Быстрое действие после анализа еды")


async def answer_food_action(callback: types.CallbackQuery, action: str):
    telegram_id = callback.from_user.id
    prompt = food_action_prompt(action)

    if not prompt:
        await callback.answer("Не понял действие")
        return

    await callback.answer()

    try:
        history = get_chat_history(telegram_id, limit=12)
        follow_up_focus_context, meal_thread = build_follow_up_focus_context(history)

        context_input = [
            build_user_memory_context(telegram_id),
            follow_up_focus_context,
        ] + meal_thread + [
            {
                "role": "system",
                "content": (
                    "Продолжай разговор по последнему анализу еды. "
                    "Не используй полный шаблон анализа. Отвечай коротко, живо и по делу. "
                    "Не используй Markdown-разметку: без **жирного**, ### и списков через дефис."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
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

        answer = normalize_telegram_markdown(response.output_text).strip()

        if action == FOOD_ACTION_SAVE_HABIT:
            habit = re.sub(r"^Привычка:\s*", "", answer).strip()
            if not habit:
                habit = "Делать один маленький шаг для улучшения похожего приёма пищи."

            status = save_user_memory_fact(telegram_id, f"Привычка: {habit}")
            if status == "duplicate":
                await callback.message.answer(
                    "Такая привычка уже сохранена в памяти.",
                    reply_markup=hide_keyboard(),
                )
                return

            await callback.message.answer(
                f"Сохранил привычку ✅\n\n{habit}",
                reply_markup=hide_keyboard(),
            )
            return

        supabase.table("messages").insert({
            "telegram_id": telegram_id,
            "role": "user",
            "content": f"[Кнопка: {food_action_label(action)}]",
        }).execute()

        supabase.table("messages").insert({
            "telegram_id": telegram_id,
            "role": "assistant",
            "content": answer,
        }).execute()

        await callback.message.answer(answer, reply_markup=hide_keyboard())

    except Exception as e:
        print("FOOD ACTION ERROR:", repr(e))
        await callback.message.answer(
            "Не смог сейчас продолжить разбор. Попробуй написать вопрос текстом.",
            reply_markup=hide_keyboard(),
        )


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
                            "пиши на 'ты' и не заполняй блоки механически, если они не нужны. "
                            "назови реальные плюсы, если они есть. Если здесь действительно есть "
                            "что улучшать — тогда предложи улучшение и один маленький шаг. Если "
                            "приём пищи и так выглядит удачным, прямо скажи это и не выдумывай "
                            "критику ради шаблона. "
                            "Не выдумывай детали, которых на фото не видно. Если не уверен, что именно "
                            "изображено или как это приготовлено, прямо скажи об этом и при необходимости "
                            "задай один короткий уточняющий вопрос. "
                            "Не используй орехи и семена как универсальное улучшение по умолчанию. "
                            "Предлагай их только если они действительно решают конкретную слабую сторону "
                            "этого блюда. Если блюдо уже сбалансировано, лучше скажи, что улучшения "
                            "не обязательны. Если это десерт или сладкий перекус, не делай орехи/семена "
                            "главным автоматическим советом; лучше предложи контекст, порцию, частоту "
                            "или сочетание с нормальным белковым приёмом пищи, если это уместно. "
                            "Перед финальным ответом сверь видимые ингредиенты и читаемый состав с долговременной "
                            "памятью пользователя. Упоминай ограничения только если на фото виден или в составе "
                            "указан продукт, который пользователь не ест, не переносит или отметил как ограничение. "
                            "Не хвали фото за отсутствие запрещённого продукта и не пиши 'нет X, это хорошо'. "
                            "Если конфликт есть, скажи, что в составе есть нежелательный для пользователя "
                            "продукт/компонент, и предложи простую замену. Такой продукт нельзя записывать "
                            "в плюсы блюда для этого пользователя. "
                            "Если улучшение уместно, предложи 1-3 конкретных варианта под это блюдо, "
                            "а не общий совет ради заполнения шаблона. "
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

        answer = normalize_good_meal_analysis(response.output_text)

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

        await message.answer(answer, reply_markup=food_analysis_actions_keyboard())

    except Exception as e:
        print("PHOTO ANALYSIS ERROR:", repr(e))
        await message.answer(
            "Не смог проанализировать фото. Попробуй отправить другое изображение или описать еду текстом.",
            reply_markup=hide_keyboard()
        )


async def analyze_food_text(message: types.Message):
    telegram_id = message.from_user.id
    text = message.text

    if not text:
        await message.answer(
            "Пока я умею анализировать только текст и фото еды.",
            reply_markup=hide_keyboard()
        )
        return

    if is_memory_save_request(text):
        await prompt_memory_save_via_menu(message)
        return

    try:
        history = get_chat_history(telegram_id, limit=12)
    except Exception as e:
        print("CHAT HISTORY ERROR:", repr(e))
        history = []

    is_analysis_request = is_meal_analysis_request(text)
    is_follow_up_request = is_meal_follow_up_request(text, history)
    is_offer_acceptance_request = is_assistant_offer_acceptance(text, history)
    is_capability_request = is_capability_question(text)

    if (
        not is_analysis_request
        and not is_follow_up_request
        and not is_offer_acceptance_request
        and not is_capability_request
        and not is_nutrition_related(text, history=history)
    ):
        await message.answer(
            (
                "Я могу помочь с питанием, привычками, самочувствием после еды, "
                "энергией, сном, тренировками и мягким улучшением образа жизни. "
                "Напиши вопрос в этих темах — разберём спокойно и по делу."
            ),
            reply_markup=hide_keyboard()
        )
        return

    try:
        supabase.table("messages").insert({
            "telegram_id": telegram_id,
            "role": "user",
            "content": text
        }).execute()

        response_instruction = (
            FOOD_ANALYSIS_FORMAT_INSTRUCTION
            if is_analysis_request
            else (
                MEAL_FOLLOW_UP_INSTRUCTION
                if is_follow_up_request
                else (
                    CONTINUE_ASSISTANT_OFFER_INSTRUCTION
                    if is_offer_acceptance_request
                    else (
                        CAPABILITY_QUESTION_INSTRUCTION
                        if is_capability_request
                        else GENERAL_NUTRITION_ADVICE_INSTRUCTION
                    )
                )
            )
        )

        context_history = history
        extra_system_context = []

        if is_follow_up_request:
            follow_up_focus_context, meal_thread = build_follow_up_focus_context(history)
            extra_system_context.append(follow_up_focus_context)
            context_history = meal_thread

        context_input = [
            build_user_memory_context(telegram_id)
        ] + extra_system_context + context_history + [
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

        answer = normalize_telegram_markdown(response.output_text)

        if is_analysis_request:
            answer = normalize_good_meal_analysis(answer)

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

        await message.answer(
            answer,
            reply_markup=(
                food_analysis_actions_keyboard()
                if is_analysis_request
                else hide_keyboard()
            ),
        )

    except Exception as e:
        print("OPENAI ERROR:", repr(e))
        await message.answer(
            "Не смог сейчас проанализировать сообщение.",
            reply_markup=hide_keyboard()
        )
