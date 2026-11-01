

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

# Деплой на прод
Сервер: `/home/kuma/charger_back` (git от пользователя `kuma`). Обновление:

```bash
git pull --ff-only && docker compose -f docker-compose.prod.yml up -d --build
```

**Перезапуск бэкенда рвёт WebSocket со всеми станциями и прерывает идущие зарядки.** Станция
возвращается сама примерно через 5 минут и присылает отложенный `StopTransaction`, но водитель
уже недозаряжен. Поэтому выкатывайте, когда нет активных сессий: на дашборде панели счётчик
«Заряжается» должен быть 0 (или проверьте `ChargingSession` в статусах `preparing`/`charging`).
После деплоя убедитесь, что станции снова «На связи».
