import difflib
import logging
import re
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.spell_corrector import correct_spelling
from app.services.ollama import correct_text, explain_error, answer_question

router = APIRouter()
log = logging.getLogger("rus_corrector")

# Эти слова и их формы не должны меняться автоматическими корректорами.
# Защищаем их до SAGE и LLM, а затем возвращаем исходные формы.
PROTECTED_WORD_RE = re.compile(
    r"(?<!\w)(?:созвон\w*|позвон\w*|звонок\w*|код\w*|кодить|баг\w*|фикс\w*)(?!\w)",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(r"ZXQPROTECTED\d{4}QXZ", re.IGNORECASE)


class CheckRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20_000)


class ErrorItem(BaseModel):
    type: str
    fragment: str
    suggestion: str
    reason: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None


class CheckResponse(BaseModel):
    errors: List[ErrorItem]
    corrected_text: str


class ChatRequest(BaseModel):
    question: str = Field(...)
    text: Optional[str] = Field(default="")


class ChatResponse(BaseModel):
    answer: str


def protect_terms(text: str):
    mapping = {}

    def replace(match):
        placeholder = f"ZXQPROTECTED{len(mapping):04d}QXZ"
        mapping[placeholder] = match.group(0)
        return placeholder

    return PROTECTED_WORD_RE.sub(replace, text), mapping


def restore_terms(text: str, mapping: dict) -> str:
    # Отмечаем маркеры, которые модель сохранила, до их замены на оригинальные слова.
    missing = []
    for marker, original in mapping.items():
        if re.search(re.escape(marker), text, flags=re.IGNORECASE):
            text = re.sub(re.escape(marker), lambda _m: original, text, flags=re.IGNORECASE)
        else:
            missing.append(original)

    # Защитный fallback на случай, если модель испортила маркер и выдала
    # вместо него другой термин из защищённой группы.
    if missing:
        candidates = list(PROTECTED_WORD_RE.finditer(text))
        for original, match in zip(missing, candidates):
            text = text[:match.start()] + original + text[match.end():]
    return text


def _classify_change(fragment: str, suggestion: str) -> str:
    # Чистые изменения знаков препинания.
    punctuation = re.compile(r"^[\W_]*$", re.UNICODE)
    if (fragment or suggestion) and punctuation.fullmatch(fragment or "") and punctuation.fullmatch(suggestion or ""):
        return "punct"

    old_words = re.findall(r"\w+", fragment, flags=re.UNICODE)
    new_words = re.findall(r"\w+", suggestion, flags=re.UNICODE)
    if len(old_words) != len(new_words):
        return "syntax"
    return "grammar"


def _diff_errors(original: str, corrected: str) -> list[dict]:
    # Токены сохраняют знаки препинания и пробельные участки, а offsets позволяют
    # подсвечивать нужное место, даже если фрагмент встречается в тексте несколько раз.
    token_re = re.compile(r"\w+|[^\w\s]|\s+", re.UNICODE)
    old_matches = list(token_re.finditer(original))
    new_matches = list(token_re.finditer(corrected))
    old_tokens = [m.group(0) for m in old_matches]
    new_tokens = [m.group(0) for m in new_matches]
    matcher = difflib.SequenceMatcher(a=old_tokens, b=new_tokens, autojunk=False)
    errors = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        if i1 < i2:
            start = old_matches[i1].start()
            end = old_matches[i2 - 1].end()
            raw_fragment = original[start:end]
            # Не создаём карточки для одних только пробелов/переносов строк.
            left_trim = len(raw_fragment) - len(raw_fragment.lstrip())
            fragment = raw_fragment.strip()
            start += left_trim
            end = start + len(fragment)
        else:
            start = end = old_matches[i1].start() if i1 < len(old_matches) else len(original)
            fragment = ""

        suggestion = "".join(new_tokens[j1:j2]).strip()
        if not fragment and not suggestion:
            continue
        # Пропускаем чистые отличия форматирования.
        if not fragment and not re.search(r"[^\s]", suggestion):
            continue
        if fragment == suggestion:
            continue

        errors.append({
            "type": _classify_change(fragment, suggestion),
            "fragment": fragment,
            "suggestion": suggestion,
            "reason": None,
            "start": start,
            "end": end,
        })

    # Удаляем дубликаты одинакового изменения в одной позиции, сохраняя порядок.
    unique = []
    seen = set()
    for err in errors:
        key = (err["start"], err["end"], err["fragment"], err["suggestion"])
        if key not in seen:
            seen.add(key)
            unique.append(err)
    return unique


@router.post("/check", response_model=CheckResponse)
async def check_text(payload: CheckRequest):
    original_text = payload.text.strip()
    protected_text, protected_mapping = protect_terms(original_text)

    # 1. Орфография. Защищённые термины передаются модели как маркеры.
    spell_corrected = correct_spelling(protected_text)

    # 2. Грамматика, пунктуация и речевые ошибки.
    llm_corrected = correct_text(spell_corrected)
    final_protected = llm_corrected if llm_corrected and "Примечание:" not in llm_corrected else spell_corrected
    final_text = restore_terms(final_protected, protected_mapping)

    # Сохраняем абзацы, но удаляем только очевидный мусор форматирования.
    final_text = re.sub(r"\(\s*\)", "", final_text)
    final_text = re.sub(r"[ \t]+\n", "\n", final_text)
    final_text = re.sub(r"\n{3,}", "\n\n", final_text).strip()

    errors = _diff_errors(original_text, final_text)

    for err in errors:
        if err["type"] == "punct":
            # Для пунктуации тоже даём контекстное объяснение, если модель доступна.
            try:
                err["reason"] = explain_error(
                    err["fragment"] or "(знак отсутствует)",
                    err["suggestion"] or "(удалить знак)",
                    original_text,
                    error_type="punct",
                ) or "Изменение связано с пунктуацией; проверьте знак в контексте предложения."
            except Exception:
                err["reason"] = "Изменение связано с пунктуацией."
        else:
            try:
                err["reason"] = explain_error(
                    err["fragment"], err["suggestion"], original_text, error_type=err["type"]
                ) or "Возможная ошибка. Сравните фрагмент с контекстом предложения."
            except Exception:
                err["reason"] = "Возможная ошибка. Сравните фрагмент с контекстом предложения."

    return CheckResponse(errors=errors, corrected_text=final_text)


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    answer = answer_question(payload.question, payload.text)
    return ChatResponse(answer=answer)