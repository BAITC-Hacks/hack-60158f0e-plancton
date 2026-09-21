#!/usr/bin/env python3
"""Классификатор обращений: категория + черновик ответа.

По умолчанию работает офлайн на правилах.
С флагом --llm категории размечаются одним вызовом Claude API.

    python3 classify.py [messages.txt] [--llm]
"""

import json
import os
import re
import sys

CATEGORIES = ("справка", "жалоба", "другое")

# --- правила ---------------------------------------------------------------

COMPLAINT_PATTERNS = [
    r"не работа", r"не раб\b", r"пропал", r"сломал", r"слома\b",
    r"холодн", r"очеред", r"грязн", r"жалоб", r"ужасн", r"отврат",
    r"хамств", r"груб", r"шум", r"течёт", r"течет", r"протека",
    r"долго жд", r"не убира", r"не выда", r"отказал", r"плохо\b",
]

CERTIFICATE_PATTERNS = [
    r"справк", r"выписк", r"подтвержд", r"заверен",
    r"характеристик", r"копи\w* диплом", r"академическ\w* отпуск",
]

# Тема обращения задаёт содержательный черновик, категория — тон.
# Для темы можно описать разные ответы по категориям; если для категории
# ответа нет, берётся общий шаблон из FALLBACK_REPLIES.
TOPICS = {
    "study_certificate": {
        # узкий паттерн: просто слово «справка» темой не считается,
        # иначе «справка для бассейна» получит ответ про место учёбы
        "pattern": r"справк\w*\s+(?:о\s+мест|об\s+обучен|из\s+вуза)"
                   r"|мест\w*\s+уч[ёе]б",
        "replies": {
            "справка":
                "Здравствуйте! Справку о месте учёбы можно заказать в деканате "
                "или через личный кабинет в разделе «Заявления». Срок подготовки — "
                "до 3 рабочих дней, документ выдаётся на руки или отправляется на почту. "
                "Уточните, пожалуйста, нужен ли вам оригинал с печатью.",
            "жалоба":
                "Здравствуйте! Сожалеем, что справку не выдали вовремя. "
                "Обращение зарегистрировано, мы уточним статус заявки в деканате "
                "и сообщим срок готовности документа. Напишите, пожалуйста, "
                "когда и каким способом вы её заказывали.",
        },
    },
    "food": {
        "pattern": r"столов|буфет|еда|еду\b|питани|обед",
        "replies": {
            "жалоба":
                "Здравствуйте! Спасибо за сигнал — передали информацию в службу "
                "организации питания. Проверим температуру блюд на линии раздачи и "
                "загрузку касс в часы пик. Напишите, пожалуйста, в какое время и в "
                "какой столовой это было, чтобы мы точнее разобрались.",
        },
    },
    "wifi": {
        "pattern": r"wi-?fi|вай-?фай|интернет|сет[ьи]\b",
        "replies": {
            "жалоба":
                "Здравствуйте! Зафиксировали проблему с Wi-Fi и передали заявку в "
                "IT-службу. Специалисты проверят точки доступа в указанном корпусе. "
                "Ориентировочный срок — в течение рабочего дня; о результате сообщим "
                "ответом на это обращение.",
            "другое":
                "Здравствуйте! Подскажите, пожалуйста, корпус и устройство — "
                "подскажем, к какой сети подключаться и какие данные для входа "
                "использовать. Если сеть не находится, оформим заявку в IT-службу.",
        },
    },
    "appointment": {
        "pattern": r"запис\w*ся|записать|консультац|приём|прием\b|встреч",
        "replies": {
            "другое":
                "Здравствуйте! Записаться на консультацию можно через личный кабинет "
                "в разделе «Запись» или ответом на это письмо. Подскажите, пожалуйста, "
                "удобное время и тему консультации — подберём ближайший свободный слот "
                "и пришлём подтверждение.",
        },
    },
    "parking": {
        "pattern": r"парков|автомобил|машин",
        "replies": {
            "другое":
                "Здравствуйте! Гостевая парковка расположена у главного входа, въезд "
                "со стороны центральных ворот. Места для гостей отмечены отдельной "
                "разметкой; при въезде назовите охране цель визита. Если нужен пропуск "
                "на несколько часов, напишите дату и номер автомобиля.",
            "жалоба":
                "Здравствуйте! Приняли обращение по парковке и передали его службе "
                "эксплуатации. Уточните, пожалуйста, дату, время и корпус — проверим "
                "занятость мест и работу въезда.",
        },
    },
}

FALLBACK_REPLIES = {
    "справка": "Здравствуйте! Приняли запрос на документ. Уточните, "
               "пожалуйста, какая именно справка нужна и для чего — "
               "подскажем порядок получения и сроки.",
    "жалоба": "Здравствуйте! Спасибо, что сообщили. Обращение "
              "зарегистрировано и передано в ответственную службу. "
              "О результатах проверки сообщим дополнительно.",
    "другое": "Здравствуйте! Спасибо за обращение. Мы его получили и "
              "ответим по существу в ближайшее время. Если вопрос срочный, "
              "уточните, пожалуйста, детали.",
}


def _hits(patterns, text):
    return sum(1 for p in patterns if re.search(p, text))


def classify_by_rules(text):
    low = text.lower()
    complaint = _hits(COMPLAINT_PATTERNS, low)
    certificate = _hits(CERTIFICATE_PATTERNS, low)
    if complaint and complaint >= certificate:
        return "жалоба"
    if certificate:
        return "справка"
    return "другое"


def detect_topic(text):
    low = text.lower()
    for name, topic in TOPICS.items():
        if re.search(topic["pattern"], low):
            return name
    return None


def draft_reply(text, category):
    """Ответ выбирается по теме и категории; тема одна не перекрывает тон."""
    topic = detect_topic(text)
    if topic:
        reply = TOPICS[topic]["replies"].get(category)
        if reply:
            return reply
    return FALLBACK_REPLIES[category]


# --- вариант с LLM ---------------------------------------------------------

def classify_by_llm(messages):
    """Одним запросом размечает все обращения. При ошибке — правила."""
    from anthropic import Anthropic

    prompt = (
        "Ты классифицируешь обращения студентов в службу поддержки вуза.\n"
        "Категории: справка (запрос документа/справки), "
        "жалоба (претензия на качество услуг, поломка, неудобство), "
        "другое (всё остальное).\n"
        "Верни ТОЛЬКО JSON-массив строк — по одной категории на обращение, "
        "в том же порядке. Без пояснений.\n\n"
        + "\n".join(f"{i}. {m}" for i, m in enumerate(messages, 1))
    )

    client = Anthropic()  # ключ из ANTHROPIC_API_KEY
    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=256,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in response.content if b.type == "text")
    return parse_labels(raw, len(messages))


def parse_labels(raw, expected_count):
    """Разбирает ответ модели в список категорий (вынесено ради тестов)."""
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    labels = json.loads(raw)
    if not isinstance(labels, list):
        raise ValueError(f"ожидался JSON-массив, получено {type(labels).__name__}")
    if len(labels) != expected_count:
        raise ValueError(f"LLM вернул {len(labels)} меток вместо {expected_count}")
    return [lab if lab in CATEGORIES else "другое" for lab in labels]


# --- запуск ----------------------------------------------------------------

def read_messages(path):
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def main(argv):
    use_llm = "--llm" in argv
    args = [a for a in argv if not a.startswith("--")]
    path = args[0] if args else "messages.txt"

    if not os.path.exists(path):
        sys.exit(f"Файл не найден: {path}")

    messages = read_messages(path)
    if not messages:
        sys.exit(f"В файле {path} нет обращений")

    mode = "правила"
    if use_llm:
        try:
            categories = classify_by_llm(messages)
            mode = "LLM (claude-opus-5)"
        except Exception as exc:  # нет ключа, нет сети, кривой ответ
            print(f"[!] LLM недоступен ({exc}); переключаюсь на правила\n",
                  file=sys.stderr)
            categories = [classify_by_rules(m) for m in messages]
    else:
        categories = [classify_by_rules(m) for m in messages]

    print(f"Обращений: {len(messages)} · режим классификации: {mode}\n")
    for i, (text, category) in enumerate(zip(messages, categories), 1):
        print(f"{i}) {text}")
        print(f"   Категория: {category}")
        print(f"   Ответ: {draft_reply(text, category)}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
