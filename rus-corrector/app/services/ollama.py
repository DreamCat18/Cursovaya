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

# ==========================================
# 1. ИСПРАВЛЕНИЕ ТЕКСТА
# ==========================================
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

# ==========================================
# 2. ОБЪЯСНЕНИЕ ОШИБОК (СПИСОК СЛЕВА)
# ==========================================
EXPLAIN_SYSTEM_PROMPT = """Ты — преподаватель русского языка как иностранного.
Твоя задача — дать ОДНО короткое и понятное объяснение ошибки.
Не пиши вводных слов, не пересказывай текст, отвечай строго по делу."""

EXPLAIN_PROMPT = """Кратко объясни, почему вариант «{suggestion}» правильнее, чем «{fragment}».
Ответ должен быть не длиннее 15 слов.
Если это пунктуация, просто напиши: «Нужна запятая» или «Лишний знак».
Объяснение:"""

def explain_error(fragment: str, suggestion: str, context: str = "") -> str:
    prompt = EXPLAIN_PROMPT.format(
        fragment=fragment or "(пропущенный знак)",
        suggestion=suggestion or "(удалить)",
    )
    result = _generate(prompt, system_prompt=EXPLAIN_SYSTEM_PROMPT, temperature=0.0)
    
    if not result:
        return "Исправление соответствует нормам русского языка."
        
    # Защита интерфейса от многословного ответа модели
    result = re.sub(r"^(объяснение|краткое объяснение)\s*:\s*", "", result, flags=re.I)
    result = re.sub(r"\s+", " ", result).strip().strip('"«» ')
    
    # Обрезаем, если модель начала писать слишком много
    sentences = re.split(r"(?<=[.!?])\s+", result)
    result = sentences[0] if sentences else result
    if len(result.split()) > 25:
        result = " ".join(result.split()[:25]) + "..."
        
    return result or "Исправление соответствует нормам русского языка."

# ==========================================
# 3. ЧАТ С ПОМОЩНИКОМ
# ==========================================
CHAT_SYSTEM_PROMPT = """Ты — вежливый и точный помощник по русской грамматике. 
Твоя задача — отвечать на вопросы пользователя, связанные с правилами русского языка.
Если пользователь спрашивает о правиле, объясняй его понятно и приводи примеры.
НЕ ВЫДУМЫВАЙ слова, которых нет в вопросе. Если не знаешь ответа, вежливо скажи об этом."""

CHAT_PROMPT = """Вопрос пользователя: {question}

Текст пользователя (контекст): 
{text}

Твой ответ:"""

def answer_question(question: str, text: str) -> str:
    prompt = CHAT_PROMPT.format(
        question=question, 
        text=text[:3000] if text else "(пользователь не прикрепил текст)"
    )
    return _generate(prompt, system_prompt=CHAT_SYSTEM_PROMPT, temperature=0.4)