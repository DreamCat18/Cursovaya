from typing import Dict, List

# Проверка выполняется LLM; этот модуль оставлен для совместимости с /corpus/detect.
RULES = []


def detect_errors_by_rules(text: str) -> List[Dict[str, str]]:
    return []


def merge_errors(rule_errors: List[Dict], model_errors: List[Dict]) -> List[Dict]:
    """Объединяет совпадающие ошибки, не теряя offsets для подсветки."""
    seen = set()
    result = []
    for err in rule_errors + model_errors:
        fragment = err.get("fragment", "")
        suggestion = err.get("suggestion", "")
        if not fragment and not suggestion:
            continue
        key = (str(fragment).lower().strip(), str(suggestion).lower().strip(), err.get("start"), err.get("end"))
        if key in seen:
            continue
        seen.add(key)
        item = {
            "type": err.get("type", "grammar"),
            "fragment": fragment,
            "suggestion": suggestion,
            "reason": err.get("reason"),
        }
        if "start" in err:
            item["start"] = err["start"]
        if "end" in err:
            item["end"] = err["end"]
        result.append(item)
    return result