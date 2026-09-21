"""Классифицирует обращения из messages.txt и печатает черновики ответов."""

from pathlib import Path


INPUT_FILE = Path(__file__).with_name("messages.txt")

REFERENCE_KEYWORDS = ("справк", "где", "как получить")
COMPLAINT_KEYWORDS = ("очеред", "холодн", "пропал", "не работает", "проблем")

RESPONSES = {
    "справка": "Здравствуйте! Уточним информацию и вернёмся к вам с ответом.",
    "жалоба": "Здравствуйте! Спасибо, что сообщили. Передадим информацию ответственным и проверим ситуацию.",
    "другое": "Здравствуйте! Спасибо за обращение. Уточним детали и поможем с вашим вопросом.",
}


def classify(message: str) -> str:
    """Возвращает категорию обращения по простым ключевым словам."""
    normalized = message.lower()
    if any(keyword in normalized for keyword in COMPLAINT_KEYWORDS):
        return "жалоба"
    if any(keyword in normalized for keyword in REFERENCE_KEYWORDS):
        return "справка"
    return "другое"


def main() -> None:
    messages = INPUT_FILE.read_text(encoding="utf-8").splitlines()
    for number, message in enumerate(filter(str.strip, messages), start=1):
        category = classify(message)
        print(f"{number}. {category}\n   Обращение: {message}\n   Ответ: {RESPONSES[category]}")


if __name__ == "__main__":
    main()