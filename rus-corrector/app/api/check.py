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
    
    # 2. LLM (грамматика)
    llm_corrected = correct_text(spell_corrected)
    
    # Мягкий фильтр от "рассуждений" модели
    if not llm_corrected or "Примечание:" in llm_corrected or "Ошибка в" in llm_corrected or "В тексте есть" in llm_corrected:
        log.warning("Модель выдала рассуждения вместо текста, используем оригинал")
        final_text = spell_corrected
    else:
        final_text = llm_corrected

    # 3. Правила
    rule_errors = detect_errors_by_rules(final_text)
    
    # 4. Сравнение
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

            # ЖЕСТКИЙ ФИЛЬТР 1: Запрет на удаление (если модель удалила слово, возвращаем его)
            if tag == "delete":
                continue

            # ЖЕСТКИЙ ФИЛЬТР 2: Запрет на замену слов с разным корнем (икра -> яйцо)
            if len(frag.split()) == 1 and len(sugg.split()) == 1:
                if frag[:2].lower() != sugg[:2].lower():
                    log.warning("Отброшена замена с разным корнем: %s -> %s", frag, sugg)
                    continue

            # Определение типа
            err_type = "grammar"
            if len(frag.split()) != len(sugg.split()): err_type = "syntax"
            if len(frag) == 1 or len(sugg) == 1: err_type = "punct" # Если меняется 1 символ - пунктуация
            
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