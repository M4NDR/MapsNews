# MapsNews - Docker Setup

## Быстрый старт

### 1. Создайте файл `.env` в корне проекта:
```env
BOT_TOKEN=your_telegram_bot_token
WEBAPP_URL=http://localhost
GEOCODER_API_KEY=your_yandex_geocoder_key
REACT_APP_API_URL=http://localhost:8000
```

### 2. Запустите проект:
```bash
docker-compose up --build
```

### 3. Откройте в браузере:
- Frontend: http://localhost
- Backend API: http://localhost:8000

## Команды

```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Пересборка
docker-compose up --build

# Логи
docker-compose logs -f

# Только backend
docker-compose up backend

# Только frontend
docker-compose up frontend
```

## Структура
- `backend/` - FastAPI приложение (Python)
- `frontend/` - React приложение (Node.js + Nginx)
- `docker-compose.yml` - оркестрация сервисов

## Production
Для production измените в `docker-compose.yml`:
- Уберите volume mapping
- Настройте правильные URL
- Добавьте SSL/HTTPS
