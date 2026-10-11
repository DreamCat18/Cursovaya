"""
REST API для проверки текста и чата.
Эндпоинты:
  POST /api/check  — обнаружить ошибки в тексте
  POST /api/chat   — задать вопрос языковой модели
"""

import logging
import time
from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.services.ollama import (
    correct_text,
    explain_error,
    answer_question,
)
from app.services.parser import detect_errors_by_rules, extract_errors, merge_errors

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
        raise HTTPException(
            status_code=429,
            detail="Слишком много запросов. Подождите минуту.",
        )
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


# ===== Схемы =====
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
    """
    Проверяет текст: находит ошибки, различает их по типам,
    предлагает исправления и объясняет причину.
    """
    ip = _client_ip(request)
    _check_rate_limit(ip)

    text = payload.text

    try:
        # 1. Правила для типовых ошибок (быстро, без модели)
        rule_errors = detect_errors_by_rules(text)

        # 2. Модель: переписанный вариант текста через LLM
        corrected = correct_text(text)

        # 3. Сопоставляем исходный и исправленный текст → список ошибок
        model_errors = extract_errors(text, corrected) if corrected else []

        # 4. Объединяем, убираем дубли
        errors = merge_errors(rule_errors, model_errors)

        # 5. Для каждой ошибки просим модель объяснить причину
        for err in errors[:10]:  # ограничим до 10 объяснений за раз
            if not err.get("reason"):
                err["reason"] = explain_error(
                    fragment=err["fragment"],
                    suggestion=err["suggestion"],
                    context=text,
                )

        return CheckResponse(errors=errors)

    except HTTPException:
        raise
    except Exception as exc:
        log.error("Ошибка при проверке текста | %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Не удалось проверить текст",
        )


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    """
    Отвечает на вопрос пользователя по тексту.
    Модель не придумывает цифры — отвечает по данным системы.
    """
    ip = _client_ip(request)
    _check_rate_limit(ip)

    try:
        answer = answer_question(
            question=payload.question,
            text=payload.text or "",
        )
        return ChatResponse(answer=answer or "Не удалось получить ответ.")
    except Exception as exc:
        log.error("Ошибка чата | %s", exc)
        raise HTTPException(status_code=500, detail="Ошибка модели")