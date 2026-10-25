"""
Вспомогательные функции: объединение ошибок и сборка финального текста.
"""

import re
from typing import Dict, List


# ===== Простые правила (если понадобятся для подстраховки) =====
RULES = [
    (r"\bв Москва\b", "в Москву", "grammar",
     "Предлог «в» при указании направления требует винительного падежа."),
    (r"\bживу в Лондон\b", "живу в Лондоне", "grammar",
     "Предлог «в» при указании места требует предложного падежа."),
    (r"\bЛоедон\b", "Лондоне", "grammar",
     "Ошибка в написании названия города."),
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
    """
    Объединяет два списка ошибок, убирает дубликаты по фрагменту.
    Используется в check.py для объединения результатов SAGE и правил.
    """
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
            "type": err.get("type", "grammar"),
            "fragment": err["fragment"],
            "suggestion": err.get("suggestion", ""),
            "reason": err.get("reason"),
        })

    return result


# ===== Сборка финального текста (заглушка) =====
def build_final_text(base_text: str, errors: List[Dict]) -> str:
    """
    В текущей архитектуре финальный текст формируется через LLM (переписывание).
    Эта функция оставлена для обратной совместимости импортов.
    Возвращает текст без изменений.
    """
    return base_text