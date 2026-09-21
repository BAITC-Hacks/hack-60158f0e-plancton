#!/usr/bin/env python3
"""Тесты без зависимостей: python3 test_classify.py"""

import sys

from classify import (
    FALLBACK_REPLIES,
    TOPICS,
    classify_by_rules,
    detect_topic,
    draft_reply,
    parse_labels,
    read_messages,
)

CASES_CATEGORY = [
    # обращения из задания
    ("Как получить справку о месте учёбы?", "справка"),
    ("В столовой очередь, еда холодная.", "жалоба"),
    ("Хочу записаться на консультацию завтра.", "другое"),
    ("Пропал Wi-Fi в корпусе B.", "жалоба"),
    ("Где парковка для гостей?", "другое"),
    # жалоба важнее упоминания документа
    ("Мне уже неделю не выдают справку, это возмутительно.", "жалоба"),
    ("Нужна справка для бассейна.", "справка"),
]

failures = []


def check(condition, message):
    if not condition:
        failures.append(message)


for text, expected in CASES_CATEGORY:
    actual = classify_by_rules(text)
    check(actual == expected,
          f"категория {actual!r} вместо {expected!r} для {text!r}")

# тема не должна перекрывать тон: на жалобу не отвечаем инструкцией
complaint = "Мне уже неделю не выдают справку, это возмутительно."
reply = draft_reply(complaint, classify_by_rules(complaint))
check(reply != TOPICS["study_certificate"]["replies"]["справка"],
      "на жалобу про справку выдана инструкция по заказу справки")

# посторонняя справка не должна получать ответ про место учёбы
other_cert = "Нужна справка для бассейна."
check(detect_topic(other_cert) is None,
      "«справка для бассейна» ошибочно распознана как справка о месте учёбы")
check(draft_reply(other_cert, "справка") == FALLBACK_REPLIES["справка"],
      "для посторонней справки нужен общий шаблон с уточняющим вопросом")

# тематические ответы там, где тема распознана
check(draft_reply("Пропал Wi-Fi в корпусе B.", "жалоба")
      == TOPICS["wifi"]["replies"]["жалоба"], "ответ про Wi-Fi не подставился")
check(draft_reply("Где парковка для гостей?", "другое")
      == TOPICS["parking"]["replies"]["другое"], "ответ про парковку не подставился")

# у каждой темы ответы только для известных категорий
for name, topic in TOPICS.items():
    for category in topic["replies"]:
        check(category in FALLBACK_REPLIES,
              f"тема {name}: неизвестная категория {category!r}")

# разбор ответа LLM: голый JSON, обёртка в ``` и мусорные метки
check(parse_labels('["справка", "жалоба"]', 2) == ["справка", "жалоба"],
      "не разобран простой JSON-массив меток")
check(parse_labels('```json\n["другое"]\n```', 1) == ["другое"],
      "не снята обёртка ```json")
check(parse_labels('["выдуманная"]', 1) == ["другое"],
      "неизвестная метка должна схлопываться в «другое»")
for bad, why in [('["справка"]', "меток меньше, чем обращений"),
                 ('{"a": 1}', "ответ не массив"),
                 ('не json', "невалидный JSON")]:
    try:
        parse_labels(bad, 2)
    except Exception:
        pass
    else:
        failures.append(f"parse_labels не отверг: {why}")

# файл из задания читается и содержит 5 обращений
check(len(read_messages("messages.txt")) == 5,
      "messages.txt должен содержать 5 непустых строк")

if failures:
    print(f"ПРОВАЛЕНО ({len(failures)}):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("Все тесты пройдены")
