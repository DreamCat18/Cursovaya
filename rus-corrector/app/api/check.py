import difflib
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.spell_corrector import correct_spelling
from app.services.ollama import correct_text, explain_error, answer_question
from app.services.parser import merge_errors

router = APIRouter()
log = logging.getLogger("rus_corrector")

# Слова, которые нельзя менять
FORBIDDEN_CHANGES = {"созвон", "позвон", "звонок", "код", "кодить", "баг", "фикс"}

class CheckRequest(BaseModel):
    text: str = Field(...)

class ErrorItem(BaseModel):
    type: str
    fragment: str
    suggestion: str
    reason: Optional[str] = None

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
    text = payload.text.strip()
    
    # 1. SAGE (орфография)
    spell_corrected = correct_spelling(text)
    
    # 2. LLM (грамматика)
    llm_corrected = correct_text(spell_corrected)
    
    if not llm_corrected or "Примечание:" in llm_corrected:
        final_text = spell_corrected
    else:
        final_text = llm_corrected

    # 3. Сравнение
    errors = []
    if spell_corrected != final_text:
        orig_tokens = re.findall(r'\w+|[^\w\s]|\s+', spell_corrected)
        corr_tokens = re.findall(r'\w+|[^\w\s]|\s+', final_text)
        
        matcher = difflib.SequenceMatcher(None, orig_tokens, corr_tokens)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal": continue
            
            frag = "".join(orig_tokens[i1:i2]).strip()
            sugg = "".join(corr_tokens[j1:j2]).strip()
            
            if not frag and not sugg: continue
            if frag == sugg: continue
            if "(" in frag or ")" in frag: continue

            # Защита от удаления
            if tag == "delete": continue

            # Защита сленга
            if any(word in frag.lower() for word in FORBIDDEN_CHANGES):
                continue

            # Умный фильтр (разные корни)
            if len(frag.split()) == 1 and len(sugg.split()) == 1:
                if frag[:2].lower() != sugg[:2].lower() and len(frag) > 3:
                    continue

            err_type = "grammar"
            if len(frag.split()) != len(sugg.split()): err_type = "syntax"
            if len(frag) == 1 or len(sugg) == 1: err_type = "punct"
            
            errors.append({
                "type": err_type,
                "fragment": frag,
                "suggestion": sugg,
                "reason": None
            })

    all_errors = merge_errors([], errors)

    # Объяснения только для грамматики и синтаксиса
    for err in all_errors:
        if err["type"] in ("grammar", "syntax") and err["fragment"]:
            err["reason"] = explain_error(err["fragment"], err["suggestion"], final_text)
        elif err["type"] == "punct":
            err["reason"] = "Исправлена пунктуация."

    return CheckResponse(errors=all_errors, corrected_text=final_text)

@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    answer = answer_question(payload.question, payload.text)
    return ChatResponse(answer=answer)