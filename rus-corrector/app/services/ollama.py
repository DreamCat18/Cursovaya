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
            "stream": False,
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


SYSTEM_PROMPT = """Ты — профессиональный корректор русского языка как иностранного.
Исправляй только доказуемые языковые ошибки. Не переписывай текст ради красоты и не меняй смысл, тон, стиль, форматирование или авторскую манеру.
Разговорные слова, профессиональный сленг и современные выражения не являются ошибками сами по себе.
Не заменяй одно корректное слово другим только потому, что оно кажется более привычным.
Маркеры вида ZXQPROTECTED0000QXZ — неприкосновенные placeholders: копируй их посимвольно, не удаляй и не изменяй.
Верни только исправленный текст, без комментариев."""

CORRECT_PROMPT = """Проверь текст как корректор русского языка.
Исправляй только реальные орфографические, грамматические, пунктуационные и речевые ошибки.
Не улучшай стиль без необходимости. Не добавляй информацию, не удаляй мысли и не меняй смысл.
Сохраняй абзацы, переносы строк, разговорную лексику и профессиональные выражения, если они употреблены корректно.
Слова-маркеры ZXQPROTECTED....QXZ копируй без изменений: это защищённые фрагменты.
Если сомневаешься, является ли выражение ошибкой, оставь его как есть.
В ответе выведи ТОЛЬКО исправленный текст.

Текст:
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


EXPLAIN_PROMPT = """Ты — преподаватель русского языка как иностранного и опытный корректор.
Объясни конкретное изменение в 1–3 коротких предложениях. Учитывай контекст и не выдумывай правило.
Если исходный вариант допустим, разговорный или зависит от контекста, прямо скажи об этом и не утверждай, что это безусловная ошибка.
Для пунктуации назови знак и объясни, какое правило применимо именно в этом предложении.
Тип изменения: {error_type}
Контекст предложения/текста: {context}
Исходный фрагмент: {fragment}
Предлагаемый вариант: {suggestion}
Ответ — только объяснение, без повторения задания."""


def explain_error(fragment: str, suggestion: str, context: str, error_type: str = "grammar") -> str:
    prompt = EXPLAIN_PROMPT.format(
        fragment=fragment or "(фрагмент отсутствует)",
        suggestion=suggestion or "(удаление)",
        context=(context or "")[:1800],
        error_type=error_type,
    )
    return _generate(prompt, temperature=0.1)


CHAT_PROMPT = """Ты — помощник по русской грамматике. Отвечай кратко и учитывай контекст.
Не называй разговорное или профессиональное слово ошибкой только из-за его разговорного характера.
Текст: {text}
Вопрос: {question}
Ответ:"""


def answer_question(question: str, text: str) -> str:
    prompt = CHAT_PROMPT.format(question=question, text=text[:3000] if text else "(пусто)")
    return _generate(prompt, temperature=0.2)