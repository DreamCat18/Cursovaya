"""
Клиент vLLM: обращение к OpenAI-совместимому серверу
для исправления текста, объяснения ошибок и чата.
"""

import logging
import os

from openai import OpenAI

log = logging.getLogger("rus_corrector")

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:9900/v1")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")
VLLM_MODEL = os.getenv("VLLM_MODEL", "spell_correction")
VLLM_TIMEOUT = int(os.getenv("VLLM_TIMEOUT", "120"))

_client = OpenAI(
    base_url=VLLM_BASE_URL,
    api_key=VLLM_API_KEY,
    timeout=VLLM_TIMEOUT,
)


def _chat(prompt: str, temperature: float = 0.1, max_tokens: int = 1024) -> str:
    """Отправляет промпт в vLLM и возвращает ответ модели."""
    try:
        response = _client.chat.completions.create(
            model=VLLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            top_p=0.7,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        log.error("vLLM недоступен | %s", exc)
        return ""


def check_vllm_health() -> bool:
    """Проверяет, запущен ли сервер vLLM."""
    try:
        _client.models.list()
        return True
    except Exception:
        return False


# ===== Исправление текста =====
CORRECT_PROMPT = """Исходный текст:
{text}

Отредактируй исходный текст, исправив ошибки."""


def correct_text_with_vllm(text: str) -> str:
    """Возвращает исправленный вариант текста."""
    prompt = CORRECT_PROMPT.format(text=text)
    return _chat(prompt, temperature=0.1, max_tokens=2048)


# ===== Объяснение ошибки =====
EXPLAIN_PROMPT = """Ты — преподаватель русского языка как иностранного.
Кратко объясни причину ошибки. Ответ — одно-два предложения, без вступления.

Фрагмент с ошибкой: {fragment}
Правильный вариант: {suggestion}

Контекст:
{context}

Объяснение:"""


def explain_error(fragment: str, suggestion: str, context: str) -> str:
    """Просит модель объяснить причину ошибки простыми словами."""
    prompt = EXPLAIN_PROMPT.format(
        fragment=fragment,
        suggestion=suggestion,
        context=context[:1000],
    )
    return _chat(prompt, temperature=0.2, max_tokens=200)


# ===== Чат =====
CHAT_PROMPT = """Ты — помощник по русской грамматике для иноязычных авторов.
Отвечай по данным, которые приведены ниже. Не придумывай цифр и примеров,
которых нет в тексте. Отвечай кратко и по-русски.

Текущий текст пользователя:
{text}

Вопрос пользователя:
{question}

Ответ:"""


def answer_question(question: str, text: str) -> str:
    """Отвечает на вопрос пользователя по его тексту."""
    prompt = CHAT_PROMPT.format(
        question=question,
        text=text[:3000] if text else "(текст не введён)",
    )
    return _chat(prompt, temperature=0.3, max_tokens=512)