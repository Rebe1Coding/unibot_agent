# Ansible — деплой UniBot

## Требования

- Ansible >= 2.15 на локальной машине
- Ubuntu 22.04+ на целевом сервере
- SSH-доступ к серверу с sudo

```bash
# Установка Ansible (если нет)
pip install ansible
```

## Быстрый старт

```bash
cd infra/ansible

# 1. Скопировать и заполнить переменные
cp vars.yml.example vars.yml
nano vars.yml   # заполнить пароли, токены, IP сервера

# 2. Полный деплой (первый раз)
ansible-playbook -i inventory.yml deploy.yml -e @vars.yml

# 3. Только обновить код и перезапустить
ansible-playbook -i inventory.yml deploy.yml -e @vars.yml --tags deploy

# 4. Только обновить .env
ansible-playbook -i inventory.yml deploy.yml -e @vars.yml --tags config

# 5. Откат на предыдущий коммит
ansible-playbook -i inventory.yml rollback.yml -e @vars.yml
```

## Что делает deploy.yml

1. **setup** — обновление пакетов, установка Docker, настройка UFW
2. **deploy** — клонирование репо, генерация .env, сборка и запуск контейнеров
3. **verify** — проверка healthcheck-ов, вывод статуса

## Порты по умолчанию

| Порт | Сервис | Открыт наружу |
|------|--------|---------------|
| 22   | SSH    | да            |
| 80   | Nginx (API) | да       |
| 3000 | Grafana | да (убрать для production) |
| 8001 | Indexer UI | да (убрать для production) |
| 9001 | MinIO Console | да (убрать для production) |
