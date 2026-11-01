"""
UI-тесты для «Рус-корректор» с помощью Playwright.
Запуск из корня проекта: pytest app/tests/test_ui.py -v
"""

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://127.0.0.1:8000"

def test_tc01_load_and_check(page: Page):
    """TC-01: Загрузка текста и запуск проверки."""
    page.goto(BASE_URL)
    editor = page.locator("#editor")
    editor.click()
    editor.fill("Я ехал в Москва и говорил на русский язык")
    
    page.locator("#btn-check").click()
    
    # Ждем, пока статус изменится с "Проверяем" на "Найдено"
    # Тайм-аут увеличен до 30 секунд, чтобы модель успела ответить
    expect(page.locator("#status-text")).not_to_contain_text("Проверяем", timeout=30000)
    expect(page.locator("#status-text")).to_contain_text("Найдено ошибок", timeout=5000)


def test_tc02_text_without_errors(page: Page):
    """TC-02: Текст без ошибок."""
    page.goto(BASE_URL)
    editor = page.locator("#editor")
    editor.click()
    editor.fill("Сегодня хорошая погода. Я иду гулять в парк.")
    
    page.locator("#btn-check").click()
    
    # Ждем, пока статус изменится
    expect(page.locator("#status-text")).not_to_contain_text("Проверяем", timeout=30000)
    # Если ошибок нет, счётчик должен быть 0
    expect(page.locator("#errors-count")).to_have_text("0", timeout=5000)


def test_tc06_filter_errors(page: Page):
    """TC-06: Фильтрация ошибок по типу."""
    page.goto(BASE_URL)
    editor = page.locator("#editor")
    editor.click()
    editor.fill("Я живу в Россия. Я думаю что это правильно.")
    
    page.locator("#btn-check").click()
    
    # Ждем, пока проверка завершится
    expect(page.locator("#status-text")).not_to_contain_text("Проверяем", timeout=30000)
    
    # Нажимаем фильтр "Грамматика"
    page.locator('.chip[data-filter="grammar"]').click()
    page.wait_for_timeout(500)
    
    # В списке должны быть ошибки (если они есть)
    # Мы не проверяем конкретный текст, просто ждем, что список не пустой
    expect(page.locator("#errors-list")).not_to_contain_text("Ошибок нет", timeout=5000)


def test_tc07_copy_corrected_text(page: Page):
    """TC-07: Копирование исправленного текста."""
    page.goto(BASE_URL)
    editor = page.locator("#editor")
    editor.click()
    editor.fill("Я живу в Россия.")
    
    page.locator("#btn-check").click()
    expect(page.locator("#status-text")).not_to_contain_text("Проверяем", timeout=30000)
    
    # Переключаемся на вкладку "Исправленный текст"
    page.locator('.result-tab[data-result="corrected"]').click()
    
    copy_btn = page.locator("#btn-copy-corrected")
    expect(copy_btn).to_be_enabled(timeout=5000)


def test_tc08_chat_question(page: Page):
    """TC-08: Вопрос в чате."""
    page.goto(BASE_URL)
    
    # Открываем чат
    page.locator('.nav__btn[data-tab="chat"]').click()
    
    chat_input = page.locator("#chat-input")
    chat_input.fill("Почему слово 'вобщем' пишется как 'в общем'?")
    page.locator('#chat-form button[type="submit"]').click()
    
    # Ждем ответа модели (увеличиваем тайм-аут)
    expect(page.locator("#chat-log")).not_to_contain_text("Думаю…", timeout=60000)
    expect(page.locator("#chat-log")).to_contain_text("общем", timeout=10000)


def test_tc09_protected_slang(page: Page):
    """TC-09: Защита IT-сленга."""
    page.goto(BASE_URL)
    editor = page.locator("#editor")
    editor.click()
    editor.fill("Завтра у нас созвон по проекту.")
    
    page.locator("#btn-check").click()
    expect(page.locator("#status-text")).not_to_contain_text("Проверяем", timeout=30000)
    
    # Переключаемся на исправленный текст
    page.locator('.result-tab[data-result="corrected"]').click()
    
    expect(page.locator("#corrected-text")).to_contain_text("созвон", timeout=5000)
