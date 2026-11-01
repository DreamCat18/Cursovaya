# Рус-корректор

**Интеллектуальная система обнаружения и исправления ошибок в русскоязычных текстах иноязычных авторов**

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Ollama](https://img.shields.io/badge/Ollama-Qwen2.5-orange)](https://ollama.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

Курсовой проект по МДК.04.03 «Сопровождение интеллектуальных систем»  
Специальность 09.02.07 «Информационные системы и программирование»

---

## О проекте

Система «Рус-корректор» помогает иностранцам проверять тексты на русском языке. Она находит грамматические, орфографические и пунктуационные ошибки, объясняет их и предлагает исправленный вариант.

**Основные возможности:**
- Поиск ошибок с помощью нейросетей (SAGE и Qwen2.5)
- Подсветка ошибок прямо в тексте
- Чат с помощником по правилам русской грамматики
- Копирование готового исправленного текста

---

## Быстрый старт

### 1. Требования
- Python 3.11+
- Ollama (с моделью `qwen2.5:7b-instruct`)
- PostgreSQL (опционально)

### 2. Установка
```bash
# Клонируйте репозиторий

git clone https://github.com/ваш-логин/rus-corrector.git
cd rus-corrector

# Создайте виртуальное окружение
python -m venv .venv
source .venv/Scripts/activate  # Windows
# или source .venv/bin/activate  # Linux/WSL

# Установите зависимости
pip install -r requirements.txt

# Скачайте модель для Ollama
ollama pull qwen2.5:7b-instruct
3. Настройка
Скопируйте .env.example в .env и отредактируйте под свои нужды:

env
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
DB_HOST=localhost
DB_NAME=rus_corrector
DB_USER=postgres
DB_PASSWORD=your_password
4. Запуск
bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Откройте браузер: http://127.0.0.1:8000

Структура проекта
text
rus-corrector/
├── app/
│   ├── api/          # Эндпоинты REST API
│   ├── services/     # Логика работы с моделями
│   ├── static/       # Фронтенд (HTML, CSS, JS)
│   ├── db.py         # Подключение к PostgreSQL
│   └── main.py       # Точка входа FastAPI
├── tests/            # Автотесты
├── data/             # Логи и резервные копии
├── .env.example      # Шаблон настроек
├── requirements.txt  # Зависимости
└── README.md         # Этот файл
```
## Описание модулей

Модуль	Описание
app/api/check.py	Обработка текста: вызов моделей, сравнение, сохранение истории
app/services/ollama.py	Клиент для Qwen2.5 через Ollama
app/services/spell_corrector.py	Клиент для SAGE (орфография)
app/db.py	Настройка SQLAlchemy и сохранение истории
app/static/js/app.js	Клиентская логика и подсветка ошибок

## Тестирование

bash
# Тесты API
pytest app/tests/test_api.py -v

# UI-тесты (Playwright)
pytest app/tests/test_ui.py -v
Документация
Подробное руководство оператора и администратора находится в файле README.md (раздел «Руководство оператора»).

## Автор
Запубина А. А., группа ИСП-31, 2026 г.

## Лицензия
Проект распространяется под лицензией MIT. См. файл LICENSE.
