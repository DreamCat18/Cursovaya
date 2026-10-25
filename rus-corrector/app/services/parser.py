import re
from typing import Dict, List

# Универсальные правила для предлогов (работают для любых городов/стран)
RULES = [
    (r"\bв ([А-ЯЁ][а-яё]+)(?=\s|,|\.)", "в ${1}е", "grammar", "Предлог «в» при указании места требует предложного падежа."),
]


def detect_errors_by_rules(text: str) -> List[Dict[str, str]]:
    """
    Находит ошибки, используя универсальные правила.
    """
    errors = []
    for pattern, fix, err_type, reason in RULES:
        for match in re.finditer(pattern, text):
            word = match.group(1)
            # Пропускаем, если слово уже в предложном падеже (заканчивается на -е, -и, -у, -ю)
            if word.endswith(('е', 'и', 'у', 'ю')):
                continue
                
            errors.append({
                "type": err_type,
                "fragment": match.group(0),
                "suggestion": match.group(0) + "е", # Грубая замена
                "reason": reason,
            })
    return errors


def merge_errors(rule_errors: List[Dict], model_errors: List[Dict]) -> List[Dict]:
    seen = set()
    result = []
    for err in rule_errors + model_errors:
        if not err.get("fragment"): continue
        key = err["fragment"].lower().strip()
        if key in seen: continue
        seen.add(key)
        result.append({
            "type": err.get("type", "grammar"),
            "fragment": err["fragment"],
            "suggestion": err.get("suggestion", ""),
            "reason": err.get("reason"),
        })
    return result