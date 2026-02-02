# MapsNews 🗺️📰

Агрегатор новостей Архангельской области с привязкой событий к карте.

## 🚀 Функционал
- 📰 Сбор новостей (news29.ru) через RSS
- 📍 Геокодирование адресов (JSON-база + Yandex Maps API)
- 🌓 Темная/Светлая тема

## 🛠 Установка и запуск

### Backend (Python/FastAPI)

```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
python main.py
```

Сервер запустится на http://localhost:8000

### Frontend (React)

```bash
cd frontend
npm install
npm start
```

Приложение доступно на http://localhost:3000

## 🔧 Конфигурация
Создайте файл `.env` в папке `backend`:
```env
GEOCODER_API_KEY=ваш_ключ_яндекса
```
