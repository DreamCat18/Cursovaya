"""
Вспомогательные функции: правила для типовых ошибок,
объединение результатов и сборка финального текста.
"""

import re
from typing import Dict, List


# ===== Простые правила (подстраховка на случай, если модель пропустит) =====
RULES = [
    (r"\bв Москва\b", "в Москву", "grammar",
     "Предлог «в» при указании направления требует винительного падежа."),
    (r"\bживу в Лондон\b", "живу в Лондоне", "grammar",
     "Предлог «в» при указании места требует предложного падежа."),
    (r"\bЛоедон\b", "Лондоне", "grammar",
     "Ошибка в написании названия города."),
    (r"\bна русский язык\b", "по-русски", "grammar",
     "Наречие «по-русски» пишется через дефис."),
    (r"\bсделать решение\b", "принять решение", "lexis",
     "Устойчивое сочетание — «принять решение»."),
    (r"\bдумаю что\b", "думаю, что", "punct",
     "Перед союзом «что» ставится запятая."),
    (r"\bимею (\w+) лет\b", r"мне \1 лет", "lexis",
     "В русском языке возраст выражается конструкцией «мне ... лет»."),
    (r"\bв Турция\b", "в Турции", "grammar",
     "Предлог «в» при указании места требует предложного падежа."),
    (r"\bстолько падежи\b", "столько падежей", "grammar",
     "После «столько» существительное ставится в родительном падеже."),
]


def detect_errors_by_rules(text: str) -> List[Dict[str, str]]:
    """Находит типовые ошибки по регулярным выражениям."""
    errors = []
    for pattern, fix, err_type, reason in RULES:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            errors.append({
                "type": err_type,
                "fragment": match.group(0),
                "suggestion": fix,
                "reason": reason,
                "start": match.start(),
                "end": match.end(),
            })
    return errors


# ===== Объединение и дедупликация =====
def merge_errors(rule_errors: List[Dict], model_errors: List[Dict]) -> List[Dict]:
    """Объединяет два списка, убирает дубликаты по фрагменту."""
    seen = set()
    result = []

    for err in rule_errors + model_errors:
        if not err.get("fragment"):
            continue

        key = err["fragment"].lower().strip()
        if key in seen:
            continue
        seen.add(key)

        result.append({
            "type": err["type"],
            "fragment": err["fragment"],
            "suggestion": err.get("suggestion", ""),
            "reason": err.get("reason"),
        })

    return result


# ===== Сборка финального текста =====
def build_final_text(base_text: str, errors: List[Dict]) -> str:
    """
    Применяет правки к тексту без потери фрагментов.
    Идёт с конца текста, чтобы позиции не сдвигались.
    """
    if not errors:
        return base_text

    replacements = []  # (start, end, suggestion)

    for err in errors:
        fragment = err.get("fragment", "").strip()
        suggestion = err.get("suggestion", "")

        if not fragment:
            continue

        # Ищем фрагмент в тексте
        pos = base_text.find(fragment)
        if pos == -1:
            # Пробуем найти без учёта регистра
            pos = base_text.lower().find(fragment.lower())
        if pos == -1:
            continue

        # Не пересекаемся с уже добавленными правками
        overlap = any(
            not (pos + len(fragment) <= s or pos >= e)
            for s, e, _ in replacements
        )
        if overlap:
            continue

        replacements.append((pos, pos + len(fragment), suggestion))

    # Сортируем с конца текста
    replacements.sort(key=lambda r: r[0], reverse=True)

    result = base_text
    for start, end, suggestion in replacements:
        result = result[:start] + suggestion + result[end:]

    return result