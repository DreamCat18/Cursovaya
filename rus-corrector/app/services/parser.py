"""
Извлечение ошибок из пары «исходный — исправленный» текст.
Сравнение по словам, а не по символам.
"""

import difflib
import re
from typing import Dict, List


# ===== Простые правила для типовых ошибок =====
RULES = [
    (r"\bв Москва\b", "в Москву", "grammar",
     "Предлог «в» при указании направления требует винительного падежа."),
    (r"\bна русский язык\b", "по-русски", "grammar",
     "Наречие «по-русски» пишется через дефис."),
    (r"\bсделать решение\b", "принять решение", "lexis",
     "Устойчивое сочетание — «принять решение»."),
    (r"\bдумаю что\b", "думаю, что", "punct",
     "Перед союзом «что» ставится запятая."),
    (r"\bочень мне нравится\b", "мне очень нравится", "syntax",
     "Местоимение в дательном падеже ставится перед наречием."),
    (r"\bживу в Лондон\b", "живу в Лондоне", "grammar",
     "Предлог «в» при указании места требует предложного падежа."),
    (r"\bЛоедон\b", "Лондоне", "grammar",
     "Ошибка в написании названия города."),
    (r"\bсложная\b(?=\s+язык)", "сложный", "grammar",
     "Прилагательное согласуется с существительным в роде."),
    (r"\bсложная\b(?=\s*[.,!?])", "сложный", "grammar",
     "Прилагательное согласуется с существительным в роде."),
    (r"\bимею двадцать лет\b", "мне двадцать лет", "lexis",
     "В русском языке возраст выражается конструкцией «мне ... лет»."),
    (r"\bмама мыл\b", "мама мыла", "grammar",
     "Глагол в прошедшем времени согласуется с подлежащим в роде."),
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


# ===== Сравнение текстов по словам =====
def _tokenize(text: str) -> List[str]:
    """Разбивает текст на слова и знаки препинания, сохраняя пробелы."""
    return re.findall(r"\w+|[^\w\s]|\s+", text, flags=re.UNICODE)


def extract_errors(original: str, corrected: str) -> List[Dict[str, str]]:
    """
    Сравнивает исходный и исправленный текст по словам.
    Возвращает список правок с типом и без объяснения.
    """
    if not original or not corrected or original == corrected:
        return []

    orig_tokens = _tokenize(original)
    corr_tokens = _tokenize(corrected)

    matcher = difflib.SequenceMatcher(None, orig_tokens, corr_tokens)
    errors = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        fragment = "".join(orig_tokens[i1:i2]).strip()
        suggestion = "".join(corr_tokens[j1:j2]).strip()

        # Пустые изменения пропускаем
        if not fragment and not suggestion:
            continue

        # Если изменились только пробелы — пропускаем
        if fragment.strip() == suggestion.strip():
            continue

        # Для вставки: если вставился только знак препинания — пунктуация
        if not fragment:
            if re.fullmatch(r"[.,;:!?—–\-…]+", suggestion):
                err_type = "punct"
            else:
                err_type = "grammar"
            # Показываем соседнее слово для контекста
            left = "".join(orig_tokens[max(0, i1 - 1):i1])
            right = "".join(orig_tokens[i2:i2 + 1])
            fragment = (left + right).strip() or suggestion
        elif not suggestion:
            # Удаление
            if re.fullmatch(r"[.,;:!?—–\-…]+", fragment):
                err_type = "punct"
            else:
                err_type = "grammar"
        else:
            # Замена — определяем тип
            err_type = _guess_type(fragment, suggestion)

        errors.append({
            "type": err_type,
            "fragment": fragment,
            "suggestion": suggestion,
            "reason": None,
        })

    return errors


def _guess_type(fragment: str, suggestion: str) -> str:
    """
    Определяет тип ошибки по характеру изменения.
    """
    # Если в изменении есть знаки препинания — пунктуация
    if re.search(r"[.,;:!?—–\-…]", fragment) or re.search(r"[.,;:!?—–\-…]", suggestion):
        return "punct"

    frag_words = fragment.lower().split()
    sugg_words = suggestion.lower().split()

    # Разное число слов — синтаксис
    if len(frag_words) != len(sugg_words):
        return "syntax"

    # Если первое слово изменилось полностью
    if frag_words and sugg_words:
        fw, sw = frag_words[0], sugg_words[0]
        if fw != sw:
            # Считаем общий префикс
            common = 0
            for a, b in zip(fw, sw):
                if a == b:
                    common += 1
                else:
                    break
            # Общее начало ≥ 2 букв — грамматика (окончание или приставка)
            if common >= 2:
                return "grammar"
            # Совсем разные слова — лексика
            return "lexis"

    return "grammar"


# ===== Объединение и дедупликация =====
def merge_errors(rule_errors: List[Dict], model_errors: List[Dict]) -> List[Dict]:
    """Объединяет два списка, убирает дубликаты по фрагменту."""
    seen = set()
    result = []

    for err in rule_errors + model_errors:
        # Пропускаем ошибки без фрагмента
        if not err.get("fragment"):
            continue

        key = (err["type"], err["fragment"].lower().strip())
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