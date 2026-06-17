# Локальное развертывание для разработки

## Требования

| Инструмент | Версия | Установка |
|-----------|--------|-----------|
| Docker | 24+ | [docs.docker.com](https://docs.docker.com/engine/install/) |
| Docker Compose | v2 (плагин) | Идет вместе с Docker |
| Git | 2.30+ | `sudo apt install git` |

> **Опционально:** [uv](https://docs.astral.sh/uv/) — для запуска отдельных модулей без Docker.

## Запуск всего проекта (Docker Compose)

```bash
# 1. Клонировать
git clone https://github.com/username/unibot.git
cd unibot

# 2. Создать .env для каждого сервиса
cp university-agent/.env.example university-agent/.env
cp workers/.env.example workers/.env
cp indexer/.env.example indexer/.env
cp web-gui/.env.example web-gui/.env
cp log-viewer/.env.example log-viewer/.env
```

### Заполнить .env

Минимально необходимые переменные в каждом сервисе:

**`university-agent/.env`:**
```bash
ROUTERAI_API_KEY=sk-...       # обязательно
INTERNAL_API_KEY=change-me... # обязательно для продакшена
# Остальное можно оставить по умолчанию
```

**`workers/.env`:**
```bash
OPENAI_API_KEY=sk-...         # для Whisper API
ROUTERAI_API_KEY=sk-...       # для структурирования текста
```

### Запустить

```bash
# Все сервисы (14 контейнеров)
docker compose up -d

# Или без мониторинга (быстрее, меньше RAM)
docker compose up -d postgres redis qdrant minio \
  university-agent nginx indexer celery-worker
```

### Проверить

```bash
# Статус
docker compose ps

# Health check
curl http://localhost:80/health

# Логи агента
docker compose logs university-agent -f
```

### Доступные сервисы

| URL | Сервис |
|-----|--------|
| http://localhost:80/docs | Swagger UI (API агента) |
| http://localhost:80/gui | Web GUI (веб-интерфейс) |
| http://localhost:8001 | Indexer (управление базой знаний) |
| http://localhost:3000 | Grafana (admin/admin) |
| http://localhost:9001 | MinIO Console (minioadmin/change-me-minio-password) |
| http://localhost:6333/dashboard | Qdrant UI |
| http://localhost:5555 | Flower (мониторинг Celery) — если запущен |

## Разработка отдельных модулей

Для работы с одним модулем без пересборки Docker при каждом изменении.

### Предварительно — поднять инфраструктуру

```bash
docker compose up -d postgres redis qdrant minio
```

### university-agent (FastAPI)

```bash
cd university-agent
uv sync
cp .env.example .env
# Отредактируйте .env: замените docker-хостнеймы на localhost

uv run uvicorn app.main:app --reload --port 8000
```

### indexer

```bash
cd indexer
uv sync
cp .env.example .env
# Отредактируйте .env: замените docker-хостнеймы на localhost

uv run uvicorn indexer.main:app --reload --port 8001
```

### workers (Celery)

```bash
cd workers
uv sync
cp .env.example .env
# Отредактируйте .env: замените docker-хостнеймы на localhost

uv run celery -A workers.celery_app:app worker --loglevel=info
```

## Порядок первого запуска

1. Поднять инфраструктуру: `docker compose up -d postgres redis qdrant minio`
2. Запустить агент: `uv run uvicorn app.main:app --reload` — он создаст таблицы в PostgreSQL и коллекции в Qdrant
3. Открыть Indexer (`http://localhost:8001`) и загрузить документы в базу знаний
4. Открыть Web GUI (`http://localhost:8002`) и проверить ответ агента

## Полезные команды

```bash
# Пересобрать один сервис
docker compose build university-agent
docker compose up -d university-agent

# Посмотреть логи
docker compose logs -f university-agent

# Зайти в контейнер
docker compose exec university-agent bash

# Очистить всё (включая данные)
docker compose down -v

# Только остановить (данные сохраняются)
docker compose down
```

## Структура переменных окружения

Каждый сервис использует **свой собственный** `.env` в своей директории. Глобального `.env` нет.
Инфраструктурные переменные (PostgreSQL, Redis, MinIO) заданы напрямую в `docker-compose.yml`.

| Сервис | Файл | Ключевые переменные |
|--------|------|---------------------|
| university-agent | `university-agent/.env` | `ROUTERAI_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `QDRANT_*`, `MINIO_*` |
| workers | `workers/.env` | `CELERY_*`, `MINIO_*`, `OPENAI_API_KEY`, `ROUTERAI_API_KEY` |
| indexer | `indexer/.env` | `QDRANT_*`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` |
| web-gui | `web-gui/.env` | `API_BASE_URL`, `API_KEY` |
| log-viewer | `log-viewer/.env` | `LOG_VIEWER_*`, `DOCKER_GID` |

При локальном запуске (вне Docker) замените docker-хостнеймы на `localhost`:
- `redis:6379` → `localhost:6379`
- `postgres:5432` → `localhost:5432`
- `minio:9000` → `localhost:9000`
- `qdrant:6333` → `localhost:6333`

## Redis: разделение по базам

Redis используется тремя подсистемами, каждая в своей БД:

| БД | URL | Назначение |
|----|-----|------------|
| 0 | `redis://redis:6379/0` | Сессии диалога + семантический кеш |
| 1 | `redis://redis:6379/1` | Celery broker (очередь задач) |
| 2 | `redis://redis:6379/2` | Celery result backend (результаты) |
