""" Рус-корректор — веб-сервер на FastAPI. Запуск: uvicorn app.main:app --reload """

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.check import router as check_router
from app.api.corpus import router as corpus_router
from app.services.ollama import check_ollama_health

# ===== Логирование =====
LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("rus_corrector")

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Рус-корректор",
    description="Система обнаружения и исправления ошибок в русскоязычных текстах иноязычных авторов",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(check_router, prefix="/api", tags=["check"])
app.include_router(corpus_router, prefix="/api", tags=["corpus"])


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = BASE_DIR / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/health")
async def health():
    ollama_ok = check_ollama_health()
    return {
        "status": "ok",
        "ollama": "ok" if ollama_ok else "unavailable",
    }


@app.middleware("http")
async def journal_requests(request: Request, call_next):
    """Пишет каждый запрос и каждую ошибку в журнал."""
    import time
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("Необработанная ошибка | %s %s", request.method, request.url.path)
        return JSONResponse({"error": "Внутренняя ошибка сервера"}, status_code=500)

    if request.url.path.startswith("/api/"):
        log.info(
            "запрос | %s %s | %d | %d мс",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - start) * 1000,
        )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.error("Необработанная ошибка | %s %s | %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"error": "Внутренняя ошибка сервера"})
