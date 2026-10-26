import re
import difflib
from typing import Dict, List

RULES = [] # Правила не нужны, если работает LLM

def detect_errors_by_rules(text: str) -> List[Dict[str, str]]:
    return []

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