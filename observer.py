import os
import subprocess
import hashlib
import psutil
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Загружаем настройки
CHAT_ID = os.getenv("CHAT_ID")  # ID чата для отправки сообщений
AUTH_DURATION = timedelta(hours=1)
SESSIONS = {}  # user_id: expiry_datetime

# Создаем планировщик
scheduler = AsyncIOScheduler()

def send_usage_and_disk():
    # Отправка команды /usage
    usage_message = get_system_usage()
    # Отправка команды /disk
    disk_message = get_disk_usage()

    # Отправляем сообщение в указанный чат
    bot.send_message(CHAT_ID, usage_message)
    bot.send_message(CHAT_ID, disk_message)

def get_system_usage():
    cpu_percent = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    ram_used = ram.used / (1024 ** 3)
    ram_total = ram.total / (1024 ** 3)
    ram_percent = ram.percent

    return (
        f"📊 <b>Системные ресурсы:</b>\n"
        f"🧠 CPU: <b>{cpu_percent}%</b>\n"
        f"💾 RAM: <b>{ram_used:.2f} GB</b> / <b>{ram_total:.2f} GB</b> ({ram_percent}%)"
    )

def get_disk_usage():
    result = subprocess.run(["df", "-h"], capture_output=True, text=True)
    return f"<pre>{result.stdout}</pre>"

# Настройка планировщика для запуска каждый час
scheduler.add_job(send_usage_and_disk, 'interval', hours=1)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("🚀 Бот активирован!")

if __name__ == "__main__":
    # Запуск планировщика
    scheduler.start()
    dp.run_polling(bot)