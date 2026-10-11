""" Эндпоинты для работы с корпусом ошибок. """

import logging
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.parser import detect_errors_by_rules

router = APIRouter()
log = logging.getLogger("rus_corrector")


class ErrorTypeInfo(BaseModel):
    code: str
    label: str
    example: str
    reason: str


class CorpusInfoResponse(BaseModel):
    total_errors: int
    types: List[ErrorTypeInfo]


_ERROR_TYPES = [
    ErrorTypeInfo(
        code="grammar",
        label="Грамматика",
        example="«ехал в Москва» → «ехал в Москву»",
        reason="Предлог «в» при указании направления требует винительного падежа.",
    ),
    ErrorTypeInfo(
        code="syntax",
        label="Синтаксис",
        example="«очень мне нравится» → «мне очень нравится»",
        reason="В русском языке местоимение в дательном падеже ставится перед наречием.",
    ),
    ErrorTypeInfo(
        code="lexis",
        label="Лексика",
        example="«сделать решение» → «принять решение»",
        reason="Устойчивое сочетание — «принять решение».",
    ),
    ErrorTypeInfo(
        code="punct",
        label="Пунктуация",
        example="«думаю что» → «думаю, что»",
        reason="Перед союзом «что» ставится запятая.",
    ),
]


@router.get("/corpus/info", response_model=CorpusInfoResponse)
async def corpus_info():
    """Возвращает типы ошибок и их описание."""
    return CorpusInfoResponse(total_errors=len(_ERROR_TYPES), types=_ERROR_TYPES)


class DetectRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10_000)


@router.post("/corpus/detect")
async def corpus_detect(payload: DetectRequest):
    """Быстрая проверка по правилам, без вызова LLM."""
    try:
        errors = detect_errors_by_rules(payload.text)
        return {"errors": errors}
    except Exception as exc:
        log.error("Ошибка в corpus/detect | %s", exc)
        raise HTTPException(status_code=500, detail="Не удалось выполнить проверку")
