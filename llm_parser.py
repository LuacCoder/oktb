"""
Распознавание расписания с фотографии через OpenRouter (бесплатные vision-модели).
Ключ получи на https://openrouter.ai/keys — регается по почте, без карты.

Возвращает список записей вида:
{"group": "ИС-21", "day": "Понедельник", "pair_number": 1,
 "time": "09:00-10:30", "subject": "Матанализ", "room": "312", "teacher": "Иванов И.И."}
"""

import json
import os

from openai import OpenAI

client = OpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
)

# Бесплатная vision-модель на OpenRouter
MODEL = "qwen/qwen2.5-vl-72b-instruct:free"

EXTRACTION_PROMPT = """Ты — ассистент, который извлекает расписание занятий колледжа с фотографии таблицы расписания.

На фото может быть расписание для одной или нескольких учебных групп сразу.

Верни ТОЛЬКО валидный JSON-массив без каких-либо пояснений, комментариев или markdown-разметки, в следующем формате:

[
  {
    "group": "название группы, как написано на фото (например 'ИС-21')",
    "day": "день недели (Понедельник, Вторник, ...)",
    "pair_number": номер пары как целое число (1, 2, 3...),
    "time": "время пары, например '09:00-10:30'",
    "subject": "название предмета",
    "room": "номер аудитории, если указан, иначе пустая строка",
    "teacher": "ФИО преподавателя, если указано, иначе пустая строка"
  }
]

Правила:
- Если что-то на фото неразборчиво — сделай наиболее вероятное предположение, не оставляй поле пустым без необходимости.
- Не путай группы между собой — внимательно сопоставляй столбцы/блоки таблицы с названием группы.
- Не добавляй пары, которых нет на фото.
- Если у группы в этот день нет пары — просто не создавай для неё запись на это время.
- Названия групп приводи к единому виду (без лишних пробелов, одинаковый регистр для одной и той же группы).
- Ответ — только JSON, без ```json и без текста до/после.
"""


def parse_schedule_image(image_bytes: bytes) -> list[dict]:
    # OpenAI API ожидает base64 для изображений
    import base64

    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_image}"
                        },
                    },
                ],
            }
        ],
        max_tokens=4096,
        temperature=0.1,
    )

    text = response.choices[0].message.content.strip()

    # На случай если модель всё же обернёт ответ в ```json ... ```
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    return json.loads(text)
