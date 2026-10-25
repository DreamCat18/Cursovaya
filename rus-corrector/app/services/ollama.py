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

# СИСТЕМНЫЙ ПРОМПТ (жестко задает роль)
SYSTEM_PROMPT = """Ты — узкоспециализированный корректор. Твоя единственная задача — исправить грамматические ошибки в тексте.
Ты НЕ ведешь диалог, НЕ объясняешь правила и НЕ пишешь комментарии. Ты возвращаешь ТОЛЬКО готовый текст."""

CORRECT_PROMPT = """Исправь в тексте только падежи, предлоги и согласование в роде.
НЕ меняй правильные слова. НЕ удаляй абзацы.
Верни ТОЛЬКО исправленный текст без своих рассуждений.

Текст:
{text}"""

def correct_text(text: str) -> str:
    prompt = CORRECT_PROMPT.format(text=text)
    result = _generate(prompt, system_prompt=SYSTEM_PROMPT, temperature=0.0)
    
    # Очистка от возможного мусора, если модель все же начала рассуждать
    result = re.sub(r"^(Исправленный текст:?\s*|Вот исправленный текст:?\s*)", "", result, flags=re.IGNORECASE)
    # Убираем всё, что начинается со слов "Ошибка", "В тексте" и т.д.
    result = re.split(r"(Ошибка|В тексте|Примечание|Итоговый текст)", result)[0].strip()
    
    return result

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