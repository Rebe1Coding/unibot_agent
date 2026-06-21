<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/LangChain-0.3+-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</p>

<h1 align="center">UniBot</h1>

<p align="center">
  <b>AI-агент на основе RAG-архитектуры для информационной поддержки студентов</b>
  <br/>
  <i>Дипломный проект | Факультет компьютерных технологий и прикладной математики</i>
</p>

<p align="center">
  <a href="docs/deploy.md">Деплой</a> &nbsp;&bull;&nbsp;
  <a href="docs/development.md">Развертывание</a> &nbsp;&bull;&nbsp;
  <a href="docs/architecture.html">Архитектура</a>
</p>

---

## Что это

UniBot решает реальную проблему: сайт университета содержит актуальную информацию, но она плохо структурирована и трудна для восприятия. Агент позволяет задавать вопросы на естественном языке и получать точные ответы, основанные на актуальных данных.

**Ключевые отличия от простого чатбота:**

| | Простой чатбот | UniBot (AI-агент) |
|---|---|---|
| Источник знаний | Только обучение LLM | RAG + реальные документы вуза |
| Логика ответа | Фиксированный pipeline | Multi-step reasoning (ReAct) |
| Работа с файлами | Нет | Whisper -> Word, PDF |
| Контекст диалога | Нет / ограничен | Redis + sliding window + summary |
| Инструменты | Нет | 6 специализированных tools |
| Уточнения | Нет | Adaptive clarification strategy |

---

## Возможности

**Для абитуриентов**
- Ответы о поступлении: проходные баллы, сроки, документы
- Информация об образовательных программах
- Навигация по процессу зачисления
- Уточняющие вопросы при размытых запросах

**Для студентов**
- Конспектирование лекций: голосовое сообщение -> структурированный Word-файл
- Рекомендации учебной литературы с прямыми ссылками на скачивание
- Информация о преподавателях: предметы, контакты, расписание

**Дополнительно**
- Память диалога (6-8 последних сообщений + summary)
- Поиск в интернете, если информации нет в базе
- Ссылки на источники в каждом ответе
- Веб-интерфейс (Web GUI) с поддержкой стриминга и slash-команд

---

## Архитектура

```
                    ┌────────────────────────────────────────────┐
                    │          Nginx API Gateway (:80)           │
                    │    rate limiting · proxy · routing         │
                    └─────────────────┬──────────────────────────┘
                                      │
                    ┌─────────────────▼──────────────────────────┐
                    │        FastAPI + ReAct Agent (:8000)       │
                    │  LangChain · 6 tools · semantic cache     │
                    └──┬──────┬──────┬──────┬──────┬─────┘
                       │      │      │      │      │
              ┌────────┘  ┌───┘  ┌───┘  ┌───┘  ┌──┘
              ▼           ▼      ▼      ▼      ▼      ▼
         ┌─────────┐ ┌──────┐ ┌──────┐ ┌─────┐ ┌──────┐
         │Qdrant   │ │Redis │ │Postgr│ │MinIO│ │Celery│
         │Vector DB│ │Cache │ │SQL   │ │  S3 │ │Worker│
         └─────────┘ └──────┘ └──────┘ └─────┘ └──────┘
```

### ReAct Loop (Reasoning + Acting)

```
Вопрос студента
      │
      ▼
[Загрузка памяти из Redis]
      │
      ▼
┌─────────┐
│ THOUGHT │ ← LLM анализирует запрос + историю
└────┬────┘
     │
     ▼
┌────────┐
│ ACTION │ ← Выбор инструмента (function calling)
└────┬───┘
     │
     ├─► search_knowledge_base  (Qdrant)
     ├─► search_literature      (Qdrant + MinIO)
     ├─► get_teacher_info       (PostgreSQL)
     ├─► get_schedule           (Qdrant)
     ├─► ask_clarification      (inline-кнопки)
     ├─► search_web             (Tavily / SerpAPI)
     └─► md_to_docx_convert     (python-docx + MinIO)
          │
          ▼
   ┌─────────────┐
   │ OBSERVATION │ ← Результат инструмента
   └──────┬──────┘
          │
          ▼
   Достаточно данных?
   ├── НЕТ → THOUGHT (до 3 итераций)
   └── ДА  → FINAL ANSWER + источники + файлы
```

---

## Технологический стек

| Слой | Технология | Назначение |
|------|-----------|------------|
| **API** | FastAPI | Основной бэкенд агента |
| **AI** | LangChain + LangGraph | ReAct agent, tools, memory |
| **LLM** | GPT-4 / Claude / GigaChat | Reasoning и генерация |
| **ASR** | OpenAI Whisper | Транскрибация аудио |
| **Embeddings** | multilingual-e5-large | Векторизация (1024 dims) |
| **Vector DB** | Qdrant | RAG search, литература |
| **RDBMS** | PostgreSQL | Пользователи, преподаватели |
| **Cache** | Redis | Сессии, семантический кеш |
| **Storage** | MinIO (S3) | Аудио, Word-файлы, книги |
| **Queue** | Celery + Redis | Асинхронные задачи |
| **Frontend** | Web GUI (FastAPI + Vanilla JS) | Веб-интерфейс |
| **Gateway** | Nginx | Reverse proxy, rate limiting |
| **Monitoring** | Prometheus + Grafana | Метрики, дашборды, алерты |
| **Deploy** | Docker Compose + Ansible | Оркестрация и деплой |

---

## Структура проекта

```
unibot/
├── university-agent/        # FastAPI + ReAct Agent
│   ├── app/
│   │   ├── main.py          # API endpoints
│   │   ├── config.py        # pydantic-settings
│   │   ├── metrics.py       # Prometheus metrics
│   │   ├── agent/
│   │   │   ├── react_agent.py
│   │   │   ├── prompts.py
│   │   │   └── memory.py
│   │   ├── tools/           # 6 инструментов агента
│   │   ├── services/        # Redis, Qdrant, PostgreSQL, MinIO
│   │   └── models/          # ORM + Pydantic schemas
│   ├── Dockerfile
│   └── pyproject.toml
│
├── web-gui/                 # Веб-интерфейс (FastAPI + Vanilla JS)
│   ├── app/                 # Бэкенд: проксирование API, стриминг
│   ├── frontend/            # Статика: HTML, CSS, JS
│   ├── Dockerfile
│   └── pyproject.toml
│
├── indexer/                 # Web UI для управления базой знаний
│   ├── indexer/
│   │   ├── main.py          # FastAPI + статика
│   │   ├── parsers/         # HTML, PDF, TXT/MD
│   │   ├── chunker.py
│   │   ├── embedder.py
│   │   └── static/index.html
│   ├── Dockerfile
│   └── pyproject.toml
│
├── workers/                 # Celery Workers
│   ├── workers/
│   │   ├── celery_app.py
│   │   └── tasks/
│   │       ├── transcribe.py    # Whisper + LLM
│   │       └── generate_doc.py  # GOST Word
│   ├── Dockerfile
│   └── pyproject.toml
│
├── infra/
│   ├── nginx/nginx.conf
│   ├── monitoring/          # Prometheus + Grafana
│   ├── analytics/           # Kafka consumer
│   └── ansible/             # Deployment playbooks
│
├── docs/                    # Документация
├── docker-compose.yml       # 15 сервисов
└── .env.example
```

---

## Быстрый старт

```bash
# 1. Клонировать
git clone https://github.com/username/unibot.git
cd unibot

# 2. Настроить окружение
cp university-agent/.env.example university-agent/.env
cp workers/.env.example workers/.env
cp indexer/.env.example indexer/.env
cp web-gui/.env.example web-gui/.env
nano university-agent/.env   # заполнить API-ключи

# 3. Запустить
docker compose up -d

# 4. Готово!
# API:          http://localhost:80/docs
# Web GUI:      http://localhost:80/gui
# Indexer UI:   http://localhost:8001
# Grafana:      http://localhost:3000
# MinIO:        http://localhost:9001
# Qdrant:       http://localhost:6333/dashboard
```

Подробнее: [docs/development.md](docs/development.md)

---

## Production-деплой

```bash
cd infra/ansible
cp vars.yml.example vars.yml
nano vars.yml   # IP сервера, пароли, токены

ansible-playbook -i inventory.yml deploy.yml -e @vars.yml
```

Подробнее: [docs/deploy.md](docs/deploy.md)

---

## Документация

- [Развертывание для разработки](docs/development.md)
- [Production-деплой (Ansible)](docs/deploy.md)
- [Архитектура системы (интерактивная)](docs/architecture.html)

---

<p align="center">
  <i>Факультет компьютерных технологий и прикладной математики, 2025</i>
</p>
