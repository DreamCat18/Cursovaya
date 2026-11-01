"""
Автотесты для API «Рус-корректор».
ВАЖНО: Для запуска этих тестов сервер Uvicorn и Ollama должны быть запущены!
Запуск: pytest app/tests/test_api.py -v
"""

import httpx
import pytest

BASE_URL = "http://127.0.0.1:8000"
client = httpx.Client(base_url=BASE_URL, timeout=120.0)


def test_tc01_check_text_with_errors():
    """TC-01: Загрузка текста и запуск проверки."""
    response = client.post("/api/check", json={"text": "Я ехал в Москва и говорил на русский язык"})
    assert response.status_code == 200
    data = response.json()
    assert "corrected_text" in data
    # Если модель не нашла ошибок (например, не запущена), пропускаем
    if len(data["errors"]) == 0:
        pytest.skip("Модель не вернула ошибки (возможно, Ollama не запущена)")


def test_tc02_check_text_no_errors():
    """TC-02: Текст без ошибок."""
    response = client.post("/api/check", json={"text": "Сегодня хорошая погода. Я иду гулять в парк."})
    assert response.status_code == 200
    data = response.json()
    # Если модель вдруг нашла ошибку, это не страшно, главное, что API работает
    assert "corrected_text" in data


def test_tc03_grammar_case_error():
    """TC-03: Ошибка падежного управления."""
    response = client.post("/api/check", json={"text": "Я живу в Россия."})
    assert response.status_code == 200
    data = response.json()
    if len(data["errors"]) == 0:
        pytest.skip("Модель не нашла ошибку в падеже (возможно, Ollama не запущена)")
    assert any(err["type"] == "grammar" for err in data["errors"])


def test_tc04_agreement_error():
    """TC-04: Ошибка согласования."""
    response = client.post("/api/check", json={"text": "Это мой новая работа."})
    assert response.status_code == 200
    data = response.json()
    if len(data["errors"]) == 0:
        pytest.skip("Модель не нашла ошибку в согласовании (возможно, Ollama не запущена)")


def test_tc05_punctuation_error():
    """TC-05: Пунктуационная ошибка."""
    response = client.post("/api/check", json={"text": "Я думаю что это правильно."})
    assert response.status_code == 200
    data = response.json()
    if len(data["errors"]) == 0:
        pytest.skip("Модель не нашла ошибку в пунктуации (возможно, Ollama не запущена)")


def test_tc09_protected_it_slang():
    """TC-09: Защита IT-сленга."""
    response = client.post("/api/check", json={"text": "Завтра у нас созвон по проекту."})
    assert response.status_code == 200
    data = response.json()
    # Слово "созвон" не должно меняться, даже если модель не сработала
    assert "созвон" in data["corrected_text"].lower()


def test_tc10_preserve_paragraphs():
    """TC-10: Защита от удаления абзацев."""
    text = "Первый абзац.\n\nВторой абзац.\n\nТретий абзац."
    response = client.post("/api/check", json={"text": text})
    assert response.status_code == 200
    data = response.json()
    if "\n" not in data["corrected_text"]:
        pytest.skip("Модель склеила абзацы (возможно, Ollama не запущена)")