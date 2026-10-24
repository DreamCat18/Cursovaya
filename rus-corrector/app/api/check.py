"""
REST API для проверки текста и чата.
Эндпоинты:
  POST /api/check  — обнаружить ошибки в тексте
  POST /api/chat   — задать вопрос языковой модели
"""

import difflib
import logging
import time
from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

# Импорты сервисов
from app.services.spell_corrector import correct_spelling
from app.services.ollama import analyze_text, explain_error, answer_question
from app.services.parser import detect_errors_by_rules, merge_errors

router = APIRouter()
log = logging.getLogger("rus_corrector")

MAX_TEXT_LENGTH = 10_000
RATE_LIMIT_PER_MINUTE = 10
WINDOW_SECONDS = 60

_rate_log: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> None:
    """Проверяет, не превышен ли лимит запросов с одного адреса."""
    now = time.time()
    timestamps = [t for t in _rate_log[ip] if now - t < WINDOW_SECONDS]
    if len(timestamps) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Слишком много запросов. Подождите минуту.")
    timestamps.append(now)
    _rate_log[ip] = timestamps


def _client_ip(request: Request) -> str:
    """Возвращает реальный IP посетителя с учётом туннеля."""
    forwarded = (
        request.headers.get("cf-connecting-ip")
        or request.headers.get("x-forwarded-for")
    )
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ===== Схемы данных =====
class CheckRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH)

    @field_validator("text")
    @classmethod
    def strip_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Текст не может быть пустым")
        return v


class ErrorItem(BaseModel):
    type: str
    fragment: str
    suggestion: str
    reason: Optional[str] = None


class CheckResponse(BaseModel):
    errors: List[ErrorItem]


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    text: Optional[str] = Field(default="", max_length=MAX_TEXT_LENGTH)


class ChatResponse(BaseModel):
    answer: str


# ===== Эндпоинты =====
@router.post("/check", response_model=CheckResponse)
async def check_text(payload: CheckRequest, request: Request):
    """Проверяет текст: SAGE исправляет орфографию, LLM — грамматику."""
    ip = _client_ip(request)
    _check_rate_limit(ip)

    text = payload.text

    try:
        # 1. SAGE исправляет орфографию и опечатки
        spell_corrected = correct_spelling(text)

        # 2. Извлекаем орфографические правки через difflib
        spell_errors = []
        if spell_corrected != text:
            matcher = difflib.SequenceMatcher(None, text, spell_corrected)
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == "equal":
                    continue
                frag = text[i1:i2].strip()
                sugg = spell_corrected[j1:j2].strip()
                if frag or sugg:
                    spell_errors.append({
                        "type": "grammar",  # TODO: добавить тип "spelling"
                        "fragment": frag,
                        "suggestion": sugg,
                        "reason": "Орфографическая ошибка или опечатка.",
                    })

        # 3. Правила для типовых случаев (подстраховка)
        rule_errors = detect_errors_by_rules(spell_corrected)

        # 4. LLM анализирует уже исправленный текст на грамматику
        model_errors = analyze_text(spell_corrected)

        # 5. Объединяем и убираем дубликаты
        # (передаём сначала правила, потом модель, чтобы правила имели приоритет)
        errors = merge_errors(rule_errors + spell_errors, model_errors)

        # 6. Для ошибок без объяснения просим модель
        for err in errors[:5]:
            if not err.get("reason"):
                err["reason"] = explain_error(
                    fragment=err["fragment"],
                    suggestion=err["suggestion"],
                    context=spell_corrected,
                )

        log.info(
            "Проверка | орфография: %d, правила: %d, модель: %d, всего: %d",
            len(spell_errors), len(rule_errors), len(model_errors), len(errors)
        )

        return CheckResponse(errors=errors)

    except HTTPException:
        raise
    except Exception as exc:
        log.error("Ошибка при проверке текста | %s", exc)
        raise HTTPException(status_code=500, detail="Не удалось проверить текст")


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    """Отвечает на вопрос пользователя по тексту."""
    ip = _client_ip(request)
    _check_rate_limit(ip)

    try:
        answer = answer_question(question=payload.question, text=payload.text or "")
        return ChatResponse(answer=answer or "Не удалось получить ответ.")
    except Exception as exc:
        log.error("Ошибка чата | %s", exc)
        raise HTTPException(status_code=500, detail="Ошибка модели")