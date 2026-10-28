from typing import Dict, List


def detect_errors_by_rules(text: str) -> List[Dict]:
    """Правила корпуса можно добавить отдельно; сейчас проверяет LLM."""
    return []


def merge_errors(rule_errors: List[Dict], model_errors: List[Dict]) -> List[Dict]:
    """Объединяет ошибки, сохраняя позиции исходного и исправленного текста."""
    seen = set()
    result = []
    for err in list(rule_errors) + list(model_errors):
        fragment = str(err.get("fragment", ""))
        suggestion = str(err.get("suggestion", ""))
        start = int(err.get("start", 0) or 0)
        end = int(err.get("end", start) or start)
        corrected_start = int(err.get("corrected_start", 0) or 0)
        corrected_end = int(err.get("corrected_end", corrected_start) or corrected_start)

        if not fragment and not suggestion:
            continue
        key = (start, end, corrected_start, corrected_end, fragment, suggestion)
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "type": err.get("type", "grammar"),
            "fragment": fragment,
            "suggestion": suggestion,
            "reason": err.get("reason"),
            "start": start,
            "end": end,
            "corrected_start": corrected_start,
            "corrected_end": corrected_end,
        })
    return sorted(result, key=lambda e: (e["start"], e["end"], e["corrected_start"]))
