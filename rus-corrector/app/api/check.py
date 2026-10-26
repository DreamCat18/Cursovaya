import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.spell_corrector import correct_spelling
from app.services.ollama import correct_text, explain_error, answer_question
from app.services.parser import generate_inline_html

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
    corrected_html: str  # <-- Возвращаем размеченный HTML

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
    
    # Проверка на "бунт" модели
    if not llm_corrected or "Примечание:" in llm_corrected or len(llm_corrected) > len(spell_corrected) * 1.5:
        final_text = spell_corrected
    else:
        final_text = llm_corrected

    # 3. Генерация HTML и списка ошибок
    corrected_html, errors = generate_inline_html(spell_corrected, final_text)

    # 4. Объяснения для панели
    for err in errors[:5]:
        if err["fragment"] != "(пропущено)":
            err["reason"] = explain_error(err["fragment"], err["suggestion"], final_text)

    return CheckResponse(errors=errors, corrected_html=corrected_html)

@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    answer = answer_question(payload.question, payload.text)
    return ChatResponse(answer=answer)