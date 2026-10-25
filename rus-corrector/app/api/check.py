import difflib
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.spell_corrector import correct_spelling
from app.services.ollama import correct_text, explain_error, answer_question
from app.services.parser import detect_errors_by_rules, merge_errors

router = APIRouter()
log = logging.getLogger("rus_corrector")

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
    
    # 2. LLM (грамматика - универсально)
    llm_corrected = correct_text(spell_corrected)
    final_text = llm_corrected if llm_corrected else spell_corrected

    # 3. Правила (предлоги)
    rule_errors = detect_errors_by_rules(final_text)
    
    # 4. Сравнение текстов (по токенам, чтобы не ломать абзацы)
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

            err_type = "grammar"
            if len(frag.split()) != len(sugg.split()): err_type = "syntax"
            
            errors.append({
                "type": err_type,
                "fragment": frag,
                "suggestion": sugg,
                "reason": None
            })

    all_errors = merge_errors(rule_errors, errors)

    # 5. Объяснения
    for err in all_errors[:5]:
        if not err.get("reason"):
            err["reason"] = explain_error(err["fragment"], err["suggestion"], final_text)

    return CheckResponse(errors=all_errors, corrected_text=final_text)

@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    answer = answer_question(payload.question, payload.text)
    return ChatResponse(answer=answer)