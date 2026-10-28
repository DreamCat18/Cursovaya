import logging
import os
import re
import requests

log = logging.getLogger("rus_corrector")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))
GENERATE_URL = f"{OLLAMA_URL}/api/generate"

def _generate(prompt: str, system_prompt: str = "", temperature: float = 0.1) -> str:
    try:
        payload = {
            "model": OLLAMA_MODEL, 
            "prompt": prompt, 
            "temperature": temperature, 
            "stream": False
        }
        if system_prompt:
            payload["system"] = system_prompt
            
        response = requests.post(GENERATE_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as exc:
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

SYSTEM_PROMPT = """Ты — профессиональный лингвист-корректор. 
Твоя задача — исправлять ТОЛЬКО ошибки, не меняя смысл, стиль и структуру текста. 
Ты не ведешь диалог, не объясняешь правила и не пишешь комментарии.
НЕ трогай IT-сленг (созвон, позвон, код, баг)."""

CORRECT_PROMPT = """Ты — профессиональный корректор русского языка.
Исправляй грамматические, орфографические, пунктуационные и речевые ошибки.
Не улучшай стиль без необходимости, не добавляй информацию и не удаляй авторские мысли.
Сохраняй исходное форматирование и абзацы.
В ответе выведи ТОЛЬКО исправленный текст, без комментариев и вводных фраз.

Текст для проверки:
<text>
{text}
</text>

Исправленный текст:"""

def correct_text(text: str) -> str:
    prompt = CORRECT_PROMPT.format(text=text)
    result = _generate(prompt, system_prompt=SYSTEM_PROMPT, temperature=0.0)
    result = re.sub(r"^(Исправленный текст:?\s*|Вот исправленный текст:?\s*)", "", result, flags=re.IGNORECASE)
    result = re.sub(r"</?text>", "", result, flags=re.IGNORECASE)
    return result.strip()

EXPLAIN_PROMPT = """Объясни исправление по-русски ОДНИМ коротким предложением (не более 18 слов).
Не пересказывай контекст, не повторяй исправление, не используй вводные фразы.
Если правило нельзя уверенно определить, напиши: «Так правильно по нормам русского языка».
Фрагмент: {fragment}
Исправление: {suggestion}
Краткое объяснение:"""


def explain_error(fragment: str, suggestion: str, context: str = "") -> str:
    prompt = EXPLAIN_PROMPT.format(
        fragment=fragment or "(пропущенный знак)",
        suggestion=suggestion or "(удалить фрагмент)",
    )
    result = _generate(prompt, temperature=0.0)
    if not result:
        return "Исправление соответствует нормам русского языка."
    # Защита интерфейса от многословного ответа модели.
    result = re.sub(r"^(объяснение|краткое объяснение)\s*:\s*", "", result, flags=re.I)
    result = re.sub(r"\s+", " ", result).strip().strip('"«» ')
    sentences = re.split(r"(?<=[.!?])\s+", result)
    result = sentences[0] if sentences else result
    words = result.split()
    if len(words) > 22:
        result = " ".join(words[:22]).rstrip(" ,;:") + "…"
    return result or "Исправление соответствует нормам русского языка."

CHAT_PROMPT = """Ты — помощник по русской грамматике. Отвечай кратко по тексту.
Текст: {text}
Вопрос: {question}
Ответ:"""

def answer_question(question: str, text: str) -> str:
    prompt = CHAT_PROMPT.format(question=question, text=text[:3000] if text else "(пусто)")
    return _generate(prompt, temperature=0.3)