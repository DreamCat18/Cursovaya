import re
import difflib
from typing import Dict, List

RULES = [] # Оставляем пустым, так как основную работу делает LLM и SAGE

def detect_errors_by_rules(text: str) -> List[Dict[str, str]]:
    return []

def generate_inline_html(original: str, corrected: str) -> tuple:
    """
    Создает HTML с визуальными правками (как в Текстоводе) 
    и возвращает его вместе со списком ошибок для панели.
    """
    if original == corrected:
        return original, []

    # Разбиваем на слова и пробелы, чтобы сохранить абзацы
    orig_tokens = re.findall(r'\w+|[^\w\s]|\s+', original)
    corr_tokens = re.findall(r'\w+|[^\w\s]|\s+', corrected)

    matcher = difflib.SequenceMatcher(None, orig_tokens, corr_tokens)
    
    html_parts = []
    errors_list = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        orig_chunk = "".join(orig_tokens[i1:i2])
        corr_chunk = "".join(corr_tokens[j1:j2])

        if tag == "equal":
            html_parts.append(orig_chunk)
        else:
            # Это ошибка! Оборачиваем в HTML для визуализации
            if tag == "replace":
                # Замена: было -> стало
                safe_orig = orig_chunk
                safe_corr = corr_chunk
                
                # Добавляем в HTML
                html_parts.append(f'<span class="diff-removed">{safe_orig}</span><span class="diff-added">{safe_corr}</span>')
                
                # Добавляем в список для панели справа
                errors_list.append({
                    "type": "grammar",
                    "fragment": orig_chunk.strip(),
                    "suggestion": corr_chunk.strip(),
                    "reason": "Грамматическая или орфографическая ошибка."
                })
            
            elif tag == "insert":
                # Вставка (например, пропущенная запятая)
                safe_corr = corr_chunk
                html_parts.append(f'<span class="diff-added">{safe_corr}</span>')
                errors_list.append({
                    "type": "punct",
                    "fragment": "(пропущено)",
                    "suggestion": corr_chunk.strip(),
                    "reason": "Пропущенный элемент."
                })
                
            elif tag == "delete":
                # Удаление (например, лишняя запятая или слово)
                safe_orig = orig_chunk
                html_parts.append(f'<span class="diff-removed">{safe_orig}</span>')
                errors_list.append({
                    "type": "syntax",
                    "fragment": orig_chunk.strip(),
                    "suggestion": "(удалить)",
                    "reason": "Лишний элемент."
                })

    return "".join(html_parts), errors_list