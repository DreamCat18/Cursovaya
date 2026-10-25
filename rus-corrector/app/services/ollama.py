"""
Обёртка над Ollama: исправление текста, объяснение ошибок и чат.
"""

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
    except requests.RequestException as exc:
        log.error("Ollama недоступна | %s", exc)
        return ""


def check_ollama_health() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        models = [m.get("name", "") for m in r.json().get("models", [])]
        return any(OLLAMA_MODEL.split(":")[0] in m for m in models)
    except requests.RequestException:
        return False


CORRECT_PROMPT = """Ты — редактор русского языка. Исправь в тексте грамматические ошибки (падежи, предлоги, согласование, вид глагола), но сохрани все слова и смысл. Не удаляй слова, не сокращай текст. Верни ТОЛЬКО исправленный текст.

Текст:
{text}

Исправленный текст:"""


def correct_text(text: str) -> str:
    """Возвращает исправленный текст от LLM."""
    prompt = CORRECT_PROMPT.format(text=text)
    result = _generate(prompt, temperature=0.1)
    # Убираем возможные префиксы
    result = re.sub(r"^(Исправленный текст:?\s*)", "", result, flags=re.IGNORECASE)
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