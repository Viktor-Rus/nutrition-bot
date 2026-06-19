from clients import openai_client


def is_nutrition_related(text: str, history=None) -> bool:
    if not text:
        return True

    normalized_text = text.lower().replace("ё", "е")
    nutrition_keywords = (
        "питан",
        "еда",
        "еду",
        "продукт",
        "блюд",
        "рацион",
        "съел",
        "съела",
        "съели",
        "съем",
        "поел",
        "поела",
        "завтрак",
        "обед",
        "ужин",
        "перекус",
        "овсян",
        "молок",
        "молочн",
        "салат",
        "творог",
        "йогурт",
        "кефир",
        "сыр",
        "яйц",
        "мяс",
        "куриц",
        "индейк",
        "рыб",
        "овощ",
        "фрукт",
        "растительн",
        "альтернатив",
        "заменител",
        "орех",
        "семен",
        "авокадо",
        "масл",
        "калори",
        "белк",
        "жир",
        "углевод",
        "сахар",
        "глютен",
        "лактоз",
        "аллерг",
        "витамин",
        "бад",
        "похуд",
        "вес",
        "масса",
        "тяжест",
        "вздут",
        "изжог",
        "тошнот",
        "дискомфорт",
        "урчан",
        "бурлен",
        "газы",
        "переел",
        "переполн",
        "плохо после еды",
        "тяжело после еды",
        "чувствую тяжесть",
        "самочувствие после еды",
        "реакция на еду",
        "тяжко",
        "плохо после",
        "нехорошо после",
    )

    if any(keyword in normalized_text for keyword in nutrition_keywords):
        return True

    history_text = " ".join([
        str(item.get("content", ""))
        for item in history or []
    ]).lower().replace("ё", "е")

    follow_up_keywords = (
        "подбери",
        "давай",
        "да",
        "хочу",
        "покажи",
        "расскажи",
        "посоветуй",
        "варианты",
        "подскажи",
        "можно",
        "что лучше",
        "что мне лучше",
        "что делать",
        "что делать сейчас",
        "что сейчас делать",
        "сделать сейчас",
        "как облегчить",
        "как помочь себе",
        "что выпить",
        "после",
        "после еды",
        "после такого",
        "от этого",
        "от такого",
        "теперь",
        "стало",
        "чувствую",
        "ощущаю",
        "тяжело",
        "тяжко",
        "что это значит",
        "что это может значить",
        "что это может быть",
        "о чем это говорит",
        "о чём это говорит",
    )

    follow_up_symptom_keywords = (
        "тяжест",
        "вздут",
        "изжог",
        "тошнот",
        "дискомфорт",
        "урчит",
        "бурлит",
        "газы",
        "переел",
        "переполн",
        "сонлив",
        "слабост",
        "клонит в сон",
        "болит живот",
        "тянет живот",
        "тяжко",
        "плохо",
        "нехорошо",
    )

    action_follow_up_keywords = (
        "что делать",
        "что делать сейчас",
        "что мне лучше сделать сейчас",
        "что лучше сделать сейчас",
        "что сейчас сделать",
        "сделать сейчас",
        "как быть",
        "как облегчить",
        "как помочь",
        "как помочь себе",
        "что выпить",
        "что съесть потом",
        "что лучше дальше",
        "это нормально",
        "что это значит",
        "что это может значить",
        "что это может быть",
        "о чем это говорит",
        "о чём это говорит",
    )

    recent_nutrition_context_markers = nutrition_keywords + (
        "что это",
        "оценка",
        "что уже хорошо",
        "как улучшить",
        "маленький шаг",
        "без перфекционизма",
        "проанализируй состав",
        "состав",
        "прием пищи",
    )

    if (
        history_text
        and len(normalized_text) <= 80
        and any(keyword in normalized_text for keyword in follow_up_keywords)
        and any(keyword in history_text for keyword in recent_nutrition_context_markers)
    ):
        return True

    if (
        history_text
        and len(normalized_text) <= 160
        and any(keyword in normalized_text for keyword in follow_up_symptom_keywords)
        and any(keyword in history_text for keyword in recent_nutrition_context_markers)
    ):
        return True

    if (
        history_text
        and len(normalized_text) <= 120
        and any(keyword in normalized_text for keyword in action_follow_up_keywords)
        and any(keyword in history_text for keyword in follow_up_symptom_keywords + recent_nutrition_context_markers)
    ):
        return True

    try:
        response = openai_client.responses.create(
            model="gpt-4.1-mini",
            instructions="""
Ты классификатор.

Определи относится ли сообщение к:

- питанию
- еде
- продуктам
- здоровью
- нутрициологии
- витаминам
- минералам
- БАДам
- тренировкам
- восстановлению
- стрессу
- сну
- энергии
- метаболическому здоровью
- пищевым привычкам
- самочувствию после еды
- снижению веса
- набору массы
- анализу блюда
- списку съеденных продуктов
- описанию завтрака, обеда, ужина или перекуса

Верни строго одно слово:

YES

или

NO

Если сообщение содержит продукты, блюда или описание того, что пользователь съел или выпил, верни YES.
Если сообщение является коротким ответом на предыдущую реплику про питание, продукты или рекомендации, верни YES.
Если сомневаешься, верни YES.
""",
            input=f"""
Предыдущий контекст диалога:
{history_text or 'Нет контекста.'}

Текущее сообщение пользователя:
{text}
"""
        )

        result = response.output_text.strip().upper()
        return result == "YES"

    except Exception as e:
        print("CLASSIFIER ERROR:", repr(e))
        return True
