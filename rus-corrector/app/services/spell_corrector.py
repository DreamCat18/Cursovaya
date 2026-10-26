"""Исправление орфографии и опечаток с помощью SAGE. Работает локально."""
import logging
from functools import lru_cache

import torch
from sage.spelling_correction import T5ModelForSpellingCorruption, AvailableCorrectors

log = logging.getLogger("rus_corrector")


@lru_cache(maxsize=1)
def _get_corrector():
    try:
        corrector = T5ModelForSpellingCorruption.from_pretrained(
            AvailableCorrectors.sage_fredt5_large.value
        )
        if torch.cuda.is_available():
            corrector.model.to(torch.device("cuda:0"))
        return corrector
    except Exception as exc:
        log.error("Не удалось загрузить SAGE | %s", exc)
        return None


def correct_spelling(text: str) -> str:
    corrector = _get_corrector()
    if corrector is None:
        return text
    try:
        result = corrector.correct(text)
        if isinstance(result, list) and result:
            return result[0]
        return text
    except Exception as exc:
        log.error("Ошибка SAGE при исправлении | %s", exc)
        return text