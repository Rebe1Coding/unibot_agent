# Production-деплой UniBot

Руководство по развертыванию UniBot на production-сервере с помощью Ansible.

## Требования к серверу

| Параметр | Минимум | Рекомендуется |
|----------|---------|---------------|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Диск | 20 GB SSD | 50 GB SSD |
| ОС | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |

> Embedding-модель `multilingual-e5-large` загружается в RAM (~2 GB).
> Kafka + Zookeeper требуют ~1 GB. Остальное — PostgreSQL, Redis, Qdrant.

## Требования к локальной машине

```bash
# Ansible
pip install ansible

# SSH-ключ для сервера
ssh-keygen -t ed25519 -f ~/.ssh/unibot_deploy
ssh-copy-id -i ~/.ssh/unibot_deploy deploy@YOUR_SERVER_IP
```

## Пошаговая инструкция

### 1. Подготовка переменных

```bash
cd infra/ansible
cp vars.yml.example vars.yml
```

Заполнить `vars.yml`:

```yaml
# Обязательные
server_ip: 123.45.67.89          # IP вашего сервера
routerai_api_key: "sk-..."       # ключ RouterAI API

# Безопасность — СМЕНИТЬ ВСЕ пароли
postgres_password: "сложный_пароль_1"
minio_root_password: "сложный_пароль_2"
indexer_admin_password: "сложный_пароль_3"

# Опционально
tavily_api_key: "tvly-..."       # для веб-поиска
```

### 2. Запуск деплоя

```bash
ansible-playbook -i inventory.yml deploy.yml -e @vars.yml
```

Что произойдет:
1. Установка Docker CE на сервер
2. Настройка UFW-фаервола (только нужные порты)
3. Клонирование репозитория в `/opt/unibot`
4. Генерация `.env` из переменных
5. Сборка Docker-образов
6. Поэтапный запуск: инфраструктура -> приложения -> мониторинг
7. Проверка healthcheck всех сервисов

По завершении в консоли будут URL-ы всех сервисов.

### 3. Проверка

```bash
# С сервера
curl http://localhost:80/health

# С локальной машины
curl http://YOUR_SERVER_IP:80/health
```

Ответ:
```json
{
  "status": "ok",
  "services": {
    "redis": {"status": "ok", "latency_ms": 0.5},
    "postgres": {"status": "ok", "latency_ms": 1.2},
    "qdrant": {"status": "ok", "latency_ms": 0.8},
    "minio": {"status": "ok", "latency_ms": 0.3}
  }
}
```

## Доступные URL после деплоя

| URL | Сервис | Назначение |
|-----|--------|------------|
| `http://IP:80/docs` | Swagger UI | API-документация |
| `http://IP:80/api/chat` | API Gateway | Основной эндпоинт агента |
| `http://IP:8001` | Indexer | Управление базой знаний |
| `http://IP:80/gui` | Web GUI | Веб-интерфейс |
| `http://IP:3000` | Grafana | Мониторинг (admin/admin) |
| `http://IP:9001` | MinIO Console | Файловое хранилище |
| `http://IP:6333/dashboard` | Qdrant | Векторная БД |

## Наполнение базы знаний

После деплоя Qdrant пустой — агент не сможет отвечать. Загрузите данные:

1. Открыть `http://IP:8001` (Indexer UI)
2. Вкладка "База знаний" -> перетащить HTML/PDF/MD файлы
3. Дождаться завершения индексации
4. Вкладка "Литература" -> добавить книги (JSON или таблица)

## Обновление

```bash
# Обновить код и перезапустить
ansible-playbook -i inventory.yml deploy.yml -e @vars.yml --tags deploy
```

## Откат

```bash
# На предыдущий коммит
ansible-playbook -i inventory.yml rollback.yml -e @vars.yml

# На конкретный коммит
ansible-playbook -i inventory.yml rollback.yml -e @vars.yml -e rollback_commit=abc1234
```

## Обновление конфигурации

Если нужно сменить API-ключ, пароль или другую переменную:

```bash
# 1. Изменить vars.yml
nano vars.yml

# 2. Перегенерировать .env и перезапустить
ansible-playbook -i inventory.yml deploy.yml -e @vars.yml --tags config
```

## Бэкапы

### PostgreSQL

```bash
# На сервере
docker compose exec postgres pg_dump -U unibot university > backup_$(date +%Y%m%d).sql

# Восстановление
docker compose exec -T postgres psql -U unibot university < backup_20250413.sql
```

### Qdrant

```bash
# Снапшот коллекции
curl -X POST http://localhost:6333/collections/knowledge_base/snapshots

# Volumes хранятся в Docker named volume
docker volume inspect unibot_qdrant_data
```

### MinIO

```bash
# Все файлы в named volume
docker volume inspect unibot_minio_data
```

## Безопасность в production

**Обязательно:**
- Сменить все пароли в `vars.yml` на сложные
- Убрать порты 3000, 8001, 9001 из `open_ports` (или ограничить по IP)
- Настроить SSL через Let's Encrypt (добавить в nginx)

**Рекомендуется:**
- Настроить fail2ban для SSH
- Использовать отдельного пользователя `deploy` (не root)
- Настроить автоматические бэкапы PostgreSQL через cron

## Мониторинг

Grafana доступна на `http://IP:3000` (логин: admin / admin).

Настроенные алерты:
- **AgentDown** — агент не отвечает > 1 мин
- **HighRAGLatency** — p95 latency > 5 сек в течение 5 мин
- **HighErrorRate** — error rate > 1% в течение 5 мин
- **NoChatTraffic** — нет запросов > 30 мин

## Troubleshooting

### Контейнер не стартует

```bash
# Логи конкретного сервиса
docker compose logs university-agent --tail 50

# Статус всех контейнеров
docker compose ps
```

### Agent отвечает ошибкой

```bash
# Проверить API-ключи
docker compose exec university-agent env | grep API_KEY

# Проверить подключение к Qdrant
curl http://localhost:6333/collections
```

### Нехватка памяти

```bash
# Проверить потребление
docker stats --no-stream

# Embedding-модель занимает ~2 GB — это нормально
```
