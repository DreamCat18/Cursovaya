import logging
import os
import re
import requests

log = logging.getLogger("rus_corrector")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
GENERATE_URL = f"{OLLAMA_URL}/api/generate"

def _generate(prompt: str, temperature: float = 0.1) -> str:
    try:
        response = requests.post(
            GENERATE_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "temperature": temperature, "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as exc:
        log.error("Ollama недоступна | %s", exc)
        return ""

CORRECT_PROMPT = """Ты — профессиональный корректор русского языка. Твоя задача — исправить грамматические ошибки в тексте иностранца.
Обрати особое внимание на:
1. Согласование в роде (например, "первый проблема" -> "первая проблема", "белый вода" -> "белая вода").
2. Падежи (например, "в Россия" -> "в России", "в Турция" -> "в Турции").
3. Предлоги и виды глаголов.

КРИТИЧЕСКИЕ ПРАВИЛА:
- Сохрани ВСЕ абзацы и переносы строк. Пустая строка должна остаться пустой.
- НЕ добавляй никаких скобок, комментариев или пояснений.
- НЕ удаляй слова. Меняй только окончания или сами слова на правильные.
- Верни ТОЛЬКО исправленный текст.

Текст:
{text}

Исправленный текст:"""

def correct_text(text: str) -> str:
    prompt = CORRECT_PROMPT.format(text=text)
    result = _generate(prompt, temperature=0.0)
    result = re.sub(r"^(Исправленный текст:?\s*)", "", result, flags=re.IGNORECASE)
    result = re.sub(r"[\(\)]", "", result)
    return result.strip()

EXPLAIN_PROMPT = """Ты — преподаватель РКИ. Кратко объясни причину ошибки (1-2 предложения).
Фрагмент с ошибкой: {fragment}
Правильный вариант: {suggestion}
Объяснение:"""

def explain_error(fragment: str, suggestion: str, context: str) -> str:
    prompt = EXPLAIN_PROMPT.format(fragment=fragment, suggestion=suggestion)
    return _generate(prompt, temperature=0.2)

CHAT_PROMPT = """Ты — помощник по русской грамматике. Отвечай кратко по тексту.
Текст: {text}
Вопрос: {question}
Ответ:"""

def answer_question(question: str, text: str) -> str:
    prompt = CHAT_PROMPT.format(question=question, text=text[:3000] if text else "(пусто)")
    return _generate(prompt, temperature=0.3)