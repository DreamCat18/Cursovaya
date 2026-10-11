""" Обёртка над Ollama: вызовы локальной языковой модели для исправления текста, объяснения ошибок и чата. """

import logging
import os
import re

import requests

log = logging.getLogger("rus_corrector")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
GENERATE_URL = f"{OLLAMA_URL}/api/generate"


def _generate(prompt: str, temperature: float = 0.1) -> str:
    """Отправляет промпт в Ollama и возвращает ответ модели."""
    try:
        response = requests.post(
            GENERATE_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "temperature": temperature,
                "stream": False,
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.RequestException as exc:
        log.error("Ollama недоступна | %s", exc)
        return ""


def check_ollama_health() -> bool:
    """Проверяет, запущена ли Ollama и загружена ли модель."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        models = [m.get("name", "") for m in r.json().get("models", [])]
        return any(OLLAMA_MODEL.split(":")[0] in m for m in models)
    except requests.RequestException:
        return False


CORRECT_PROMPT = """Ты — редактор русскоязычных текстов, написанных иноязычными авторами. Исправь ошибки в исходном тексте: падежи, согласование, вид глагола, порядок слов, лексическую сочетаемость, предлоги, пунктуацию. Сохрани смысл и стиль автора. Не добавляй пояснений.

Исходный текст: {text}

Верни только исправленный текст."""


def correct_text(text: str) -> str:
    prompt = CORRECT_PROMPT.format(text=text)
    result = _generate(prompt, temperature=0.1)
    result = re.sub(r"^(Исправленный текст:?\s*)", "", result, flags=re.IGNORECASE)
    return result.strip()


EXPLAIN_PROMPT = """Ты — преподаватель русского языка как иностранного. Кратко объясни причину ошибки. Ответ — одно-два предложения, без вступления.

Фрагмент с ошибкой: {fragment}
Правильный вариант: {suggestion}

Контекст: {context}

Объяснение:"""


def explain_error(fragment: str, suggestion: str, context: str) -> str:
    prompt = EXPLAIN_PROMPT.format(
        fragment=fragment,
        suggestion=suggestion,
        context=context[:1000],
    )
    return _generate(prompt, temperature=0.2)


CHAT_PROMPT = """Ты — помощник по русской грамматике для иноязычных авторов. Отвечай по данным, которые приведены ниже. Не придумывай цифр и примеров, которых нет в тексте. Отвечай кратко и по-русски.

Текущий текст пользователя: {text}

Вопрос пользователя: {question}

Ответ:"""


def answer_question(question: str, text: str) -> str:
    prompt = CHAT_PROMPT.format(
        question=question,
        text=text[:3000] if text else "(текст не введён)",
    )
    return _generate(prompt, temperature=0.3)
