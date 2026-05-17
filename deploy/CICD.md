# CI/CD для Soft Blue Planner

Workflow `.github/workflows/deploy.yml` запускается при push в `main`:

1. ставит Python и зависимости;
2. компилирует Python-файлы;
3. собирает архив релиза без `planner.db`, `.venv`, кешей и git-метаданных;
4. загружает архив на сервер;
5. запускает `deploy/remote-deploy.sh`;
6. проверяет `https://shpull.ru/` и `/api/calendar`.

## GitHub Secrets

В настройках репозитория нужно добавить:

```text
DEPLOY_HOST=shpull.ru
DEPLOY_USER=root
DEPLOY_PORT=22
DEPLOY_PATH=/root/soft_blue_planner_crud
SERVICE_NAME=soft-blue-planner
DEPLOY_SSH_KEY=<private ssh key with access to DEPLOY_USER@DEPLOY_HOST>
```

`DEPLOY_PORT`, `DEPLOY_PATH` и `SERVICE_NAME` можно не задавать, если используются значения выше.

## Что сохраняется на сервере

Скрипт деплоя не перетирает:

- `/root/soft_blue_planner_crud/planner.db`
- `/root/soft_blue_planner_crud/.venv`

Перед каждым деплоем живая база копируется в:

```text
/root/soft_blue_planner_backups/
```
