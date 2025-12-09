import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo
from aiogram.filters import Command
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем токен из .env или вставляем сюда (для теста)
# Создайте файл .env в папке backend и добавьте туда: BOT_TOKEN=ваш_токен
TOKEN = os.getenv("BOT_TOKEN")

# Если токена нет в переменных, просим ввести
if not TOKEN:
    print("ОШИБКА: Токен бота не найден. Создайте файл .env с BOT_TOKEN=...")
    # Для быстрого теста можно раскомментировать строку ниже и вставить токен
    # TOKEN = "ВАШ_ТОКЕН_ОТ_BOTFATHER"

# Настройка URL вашего приложения
# ВАЖНО: Для локальной разработки используйте NGROK URL (https://....ngrok-free.app)
# Просто localhost не сработает в Telegram
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://news-diplom.ngrok.app") 

# Включаем логирование
logging.basicConfig(level=logging.INFO)

async def main():
    if not TOKEN:
        return

    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        kb = [
            [types.KeyboardButton(text="🗺 Открыть карту новостей", web_app=WebAppInfo(url=WEBAPP_URL))]
        ]
        keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        
        await message.answer(
            "Привет! Нажми на кнопку ниже, чтобы открыть карту новостей.",
            reply_markup=keyboard
        )

    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    if not TOKEN:
        TOKEN = input("Введите токен бота (или Ctrl+C для выхода): ").strip()
        os.environ["BOT_TOKEN"] = TOKEN
        
    print(f"Используем URL приложения: {WEBAPP_URL}")
    print("Убедитесь, что этот URL доступен из интернета (ngrok)!")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")
