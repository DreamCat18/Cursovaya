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

# Слова, которые нельзя менять (IT-сленг)
FORBIDDEN_WORDS = re.compile(r"(?<!\w)(?:созвон\w*|позвон\w*|звонок\w*|код\w*|кодить|баг\w*|фикс\w*)(?!\w)", re.IGNORECASE)

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

@router.post("/check", response_model=CheckResponse)
async def check_text(payload: CheckRequest):
    original_text = payload.text.strip()
    
    # 1. SAGE (орфография)
    try:
        spell_corrected = correct_spelling(original_text)
    except Exception as e:
        log.error("SAGE error: %s", e)
        spell_corrected = original_text

    # 2. LLM (грамматика)
    try:
        llm_corrected = correct_text(spell_corrected)
    except Exception as e:
        log.error("LLM error: %s", e)
        llm_corrected = spell_corrected

    if not llm_corrected or "Примечание:" in llm_corrected or "В тексте" in llm_corrected:
        final_text = spell_corrected
    else:
        final_text = llm_corrected

    # 3. Очистка от мусора
    final_text = re.sub(r"\(\s*\)", "", final_text)
    final_text = re.sub(r"[ \t]+\n", "\n", final_text)
    final_text = re.sub(r"\n{3,}", "\n\n", final_text).strip()

    # 4. Поиск различий (с сохранением координат)
    errors = []
    if spell_corrected != final_text:
        # Токенизация (слова, пунктуация, пробелы)
        token_re = re.compile(r"\w+|[^\w\s]|\s+", re.UNICODE)
        old_matches = list(token_re.finditer(spell_corrected))
        new_matches = list(token_re.finditer(final_text))
        
        old_tokens = [m.group(0) for m in old_matches]
        new_tokens = [m.group(0) for m in new_matches]
        
        matcher = difflib.SequenceMatcher(a=old_tokens, b=new_tokens, autojunk=False)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal": continue
            
            # Извлекаем фрагмент
            if i1 < i2:
                start = old_matches[i1].start()
                end = old_matches[i2 - 1].end()
                raw_frag = spell_corrected[start:end]
                fragment = raw_frag.strip()
                # Корректируем координаты после strip()
                left_trim = len(raw_frag) - len(raw_frag.lstrip())
                start += left_trim
                end = start + len(fragment)
            else:
                start = end = old_matches[i1].start() if i1 < len(old_matches) else len(spell_corrected)
                fragment = ""

            suggestion = "".join(new_tokens[j1:j2]).strip()
            
            if not fragment and not suggestion: continue
            if fragment == suggestion: continue
            if "(" in fragment or ")" in fragment: continue

            # ЖЕСТКИЙ БЛОК: запрет на удаление
            if tag == "delete": continue

            # Защита IT-сленга
            if FORBIDDEN_WORDS.search(fragment):
                continue

            # Фильтр замены разных корней (икра -> яйцо)
            if len(fragment.split()) == 1 and len(suggestion.split()) == 1:
                if fragment[:2].lower() != suggestion[:2].lower() and len(fragment) > 3:
                    continue

            # Определение типа (только grammar и punct)
            err_type = "grammar"
            if len(fragment) == 1 or len(suggestion) == 1 or tag == "insert":
                err_type = "punct"

            errors.append({
                "type": err_type,
                "fragment": fragment,
                "suggestion": suggestion,
                "start": start,
                "end": end,
                "reason": None
            })

    # 5. Объяснения
    for err in errors:
        if err["type"] == "punct":
            err["reason"] = "Исправлена пунктуация."
        else:
            try:
                err["reason"] = explain_error(
                    err["fragment"], err["suggestion"], spell_corrected
                ) or "Грамматическая ошибка."
            except:
                err["reason"] = "Грамматическая ошибка."

    return CheckResponse(errors=errors, corrected_text=final_text)


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    answer = answer_question(payload.question, payload.text)
    return ChatResponse(answer=answer)