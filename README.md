

Добро пожаловать! Следуйте инструкциям ниже, чтобы настроить и запустить приложение.


1. **Скопируйте файл конфигурации**

   Сначала скопируйте файл `.env.example` в файл `.env`. Это сделает его доступным для Docker:
   
   ```bash
   cp .env.example .env

2. **Запустите контейнеры**

   Используйте docker-compose для сборки и запуска контейнеров:

   ```bash
   docker-compose up
   postgres(CREATE EXTENSION IF NOT EXISTS pg_trgm;)


3. **Остановка и удаление контейнеров**

   Если вам нужно остановить и удалить контейнеры, используйте:

   ```bash
   docker-compose down
   
# Документация 
- **GET docs/**
- **GET schema/**

# Админка `/panel/`
React-админка (`admin-ui/`) работает поверх Django-приложения `app/staff/`: ресурсы описываются в
`<app>/staff.py` (`account/staff.py`, `payments/staff.py`), фронт строит экраны по `/api/staff/v1/meta/`.
Подробности — `admin-ui/AGENTS.md`. Вход — тем же номером и паролем, что в `/admin/` (нужен `is_staff`),
права на разделы — стандартные права Django. В проде статику собирает образ nginx (`nginx/Dockerfile`).

```bash
python app/manage.py staff_openapi --file admin-ui/openapi/staff.yaml   # после смены описания ресурсов
cd admin-ui && corepack pnpm install && corepack pnpm api:generate && corepack pnpm dev   # http://localhost:5173/panel/
```
