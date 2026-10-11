""" Извлечение ошибок из пары «исходный — исправленный» текст и простые правила для типовых случаев. """

import difflib
import re
from typing import Dict, List


RULES = [
    (r"\bв Москва\b", "в Москву", "grammar",
     "Предлог «в» при указании направления требует винительного падежа."),
    (r"\bна русский язык\b", "по-русски", "grammar",
     "Наречие «по-русски» пишется через дефис и не требует предлога «на»."),
    (r"\bсделать решение\b", "принять решение", "lexis",
     "Устойчивое сочетание — «принять решение»."),
    (r"\bдумаю что\b", "думаю, что", "punct",
     "Перед союзом «что» в сложноподчинённом предложении ставится запятая."),
    (r"\bочень мне нравится\b", "мне очень нравится", "syntax",
     "В русском языке местоимение в дательном падеже ставится перед наречием."),
]


def detect_errors_by_rules(text: str) -> List[Dict[str, str]]:
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


def extract_errors(original: str, corrected: str) -> List[Dict[str, str]]:
    if not original or not corrected or original == corrected:
        return []

    errors = []
    matcher = difflib.SequenceMatcher(None, original, corrected)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        fragment = original[i1:i2].strip()
        suggestion = corrected[j1:j2].strip()

        if not fragment and not suggestion:
            continue

        errors.append({
            "type": _guess_type(fragment, suggestion),
            "fragment": fragment or original[max(0, i1 - 1):i2],
            "suggestion": suggestion or "(удалить)",
            "reason": None,
            "start": i1,
            "end": i2,
        })

    return errors


def _guess_type(fragment: str, suggestion: str) -> str:
    if not fragment:
        return "punct"
    if re.search(r"[.,;:!?—–-]", fragment) or re.search(r"[.,;:!?—–-]", suggestion):
        return "punct"
    if len(fragment.split()) != len(suggestion.split()):
        return "syntax"
    if fragment.lower().split()[0:1] != suggestion.lower().split()[0:1]:
        return "lexis"
    return "grammar"


def merge_errors(rule_errors: List[Dict], model_errors: List[Dict]) -> List[Dict]:
    seen = set()
    result = []
    for err in rule_errors + model_errors:
        key = (err["type"], err["fragment"].lower().strip())
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "type": err["type"],
            "fragment": err["fragment"],
            "suggestion": err["suggestion"],
            "reason": err.get("reason"),
        })
    return result
