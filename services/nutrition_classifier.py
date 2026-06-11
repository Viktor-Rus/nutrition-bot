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
    )

    if (
        history_text
        and len(normalized_text) <= 80
        and any(keyword in normalized_text for keyword in follow_up_keywords)
        and any(keyword in history_text for keyword in nutrition_keywords)
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
