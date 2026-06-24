<div align="center">

# SciAnalyzer

**Настольное приложение для поиска, анализа и систематизации научных публикаций**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey?logo=windows)](https://www.microsoft.com/windows)
[![AI](https://img.shields.io/badge/AI-Ollama%20%7C%20Offline-green?logo=ollama)](https://ollama.com/)
[![DB](https://img.shields.io/badge/Database-SQLite-blue?logo=sqlite)](https://sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

</div>

---

## О проекте

**SciAnalyzer** — приложение для исследователей, аспирантов и студентов, которое объединяет в одном окне **7 научных баз данных**, встроенный **ИИ-помощник на базе Ollama** и полный набор инструментов для работы с документами.

Весь ИИ работает **локально и офлайн** — без передачи данных в облако.

---

## Возможности

| Модуль | Что умеет |
|---|---|
| **Поиск** | Одновременный запрос к 7 источникам: arXiv, PubMed, Semantic Scholar, КиберЛенинка, СибАК, Молодой учёный, eLibrary |
| **Разведка** | Веб-краулер по сайтам научных изданий с настройкой глубины и задержки |
| **Библиотека** | Хранение статей с PDF/TXT, теги, избранное, семантический поиск по смыслу |
| **Реферирование** | ИИ создаёт краткое резюме любой статьи (модель qwen2.5:3b) |
| **Перевод** | Автоматический перевод на русский язык |
| **Сравнение** | Анализ текстового и семантического сходства двух документов (PDF/DOCX) |
| **Документы** | Генерация отчётов по DOCX-шаблонам с переменными `{{поле}}` и выпадающими списками из БД |
| **Аналитика** | Упоминания персон, история поиска, статистика по источникам |

---

## Системные требования

| Параметр | Минимум | Рекомендуется |
|---|---|---|
| ОС | Windows 10 x64 | Windows 11 |
| RAM | 8 ГБ | 16 ГБ |
| Диск | 5 ГБ | 10 ГБ |
| CPU | 4 ядра | 8 ядер |
| Видеокарта | Не требуется | — |
| Python | 3.10+ | 3.12 |

---

## Установка для разработки

### 1. Клонировать репозиторий

```bash
git clone https://github.com/maxnetwork2025-sketch/SciAnalyzer.git
cd SciAnalyzer
```

### 2. Создать виртуальное окружение

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Установить Ollama и загрузить модели

Скачайте [Ollama для Windows](https://ollama.com/download/windows), затем:

```bash
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

### 5. Запустить приложение

```bash
python main.py
```

При первом запуске автоматически создаётся база данных и учётная запись администратора (`admin` / `admin`).

---

## Зависимости

```
customtkinter       # GUI-фреймворк
requests            # HTTP-клиент
beautifulsoup4      # Парсинг HTML
lxml                # HTML/XML-парсер
numpy               # Векторная математика для эмбеддингов
PyMuPDF             # Чтение и рендер PDF
Pillow              # Изображения из PDF-страниц
pypdf               # Извлечение текста из PDF
python-docx         # Чтение DOCX
docxtpl             # Шаблоны DOCX с Jinja2
newspaper4k         # Полнотекстовый парсинг статей по URL
curl-cffi           # TLS-имитация Chrome (для eLibrary.ru)
```

Полный список: [`requirements.txt`](requirements.txt)

---

## Структура проекта

```
SciAnalyzer/
├── main.py                  # Точка входа
├── requirements.txt
│
├── core/                    # Бизнес-логика
│   ├── api_client.py        # arXiv, PubMed, Semantic Scholar
│   ├── cyberleninka.py      # Скрапер КиберЛенинки
│   ├── sibac.py             # Скрапер СибАК
│   ├── moluch.py            # Скрапер Молодого учёного
│   ├── cyberpedia.py        # Скрапер CyberpediA
│   ├── elibrary.py          # Скрапер eLibrary.ru (с авторизацией)
│   ├── scraper.py           # Универсальный парсер статей по URL
│   ├── downloader.py        # Скачивание PDF/TXT
│   ├── summarizer.py        # Реферирование через Ollama
│   ├── translator.py        # Перевод через Ollama
│   ├── embedder.py          # Эмбеддинги через Ollama
│   ├── compare_engine.py    # Сравнение документов
│   ├── pdf_handler.py       # Просмотр PDF
│   ├── ollama_manager.py    # Управление процессом Ollama
│   └── paths.py             # Пути к данным (dev / frozen)
│
├── db/
│   ├── __init__.py          # Публичный API модуля
│   └── database.py          # SQLite-схема и все запросы
│
├── ui/                      # Интерфейс (customtkinter)
│   ├── app.py               # Главное окно с вкладками
│   ├── login.py             # Окно входа
│   ├── theme.py             # Цвета, шрифты, компоненты
│   ├── search_tab.py        # Поиск и разведка
│   ├── results_tab.py       # Библиотека статей
│   ├── documents_tab.py     # Создание документов
│   ├── compare_tab.py       # Сравнение документов
│   ├── settings_tab.py      # Настройки и пользователи
│   ├── persons_tab.py       # Аналитика персон
│   └── document_viewer.py   # Просмотр PDF/TXT
│
└── ШаблоныДокументов/       # DOCX-шаблоны (добавляются вручную)
```

---

## Хранение данных

Все пользовательские данные хранятся в `%APPDATA%\SciAnalyzer\`:

| Папка / файл | Содержимое |
|---|---|
| `scianalyzer.db` | SQLite-база: пользователи, статьи, настройки, документы |
| `НайденныеСтатьи\` | Скачанные PDF и TXT-файлы |
| `ШаблоныДокументов\` | DOCX-шаблоны с переменными `{{...}}` |
| `СозданныеДокументы\` | Сгенерированные документы |
| `models\` | Модели Ollama |

---

## ИИ-компоненты

| Компонент | Модель | Размер | Назначение |
|---|---|---|---|
| LLM | `qwen2.5:3b` | ~1.8 ГБ | Реферирование, перевод |
| Эмбеддинги | `nomic-embed-text` | ~270 МБ | Семантический поиск и сравнение |

Движок — **[Ollama](https://ollama.com/)**, работает на CPU без GPU. Все вычисления происходят локально.

---

## Внешние API

| Сервис | Ключ | Лимиты |
|---|---|---|
| arXiv | Не нужен | — |
| PubMed (NCBI) | Не нужен | 3 запроса/сек |
| Semantic Scholar | Не нужен | 1 запрос/сек |
| КиберЛенинка | Не нужен | — |
| СибАК / Молодой учёный / CyberpediA | Не нужен | — |
| **eLibrary.ru** | Логин + пароль (бесплатно) | Есть капча |

---

## Сборка в EXE

```bash
pip install pyinstaller
pyinstaller main.spec
```

Готовый дистрибутив появится в `dist\SciAnalyzer\`.

---

## Вклад в проект

1. Форкните репозиторий
2. Создайте ветку: `git checkout -b feature/my-feature`
3. Зафиксируйте изменения: `git commit -m "feat: описание"`
4. Откройте Pull Request

---

## Лицензия

Распространяется под лицензией [MIT](LICENSE).

---

<div align="center">
  Сделано для автоматизации научной работы
</div>
