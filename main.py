import os
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

def validate(user_id, chat_id: int) -> bool:
    allowed_user_ids = list(map(int, os.getenv("ALLOWED_USER_IDS").split(',')))
    allowed_chat_ids = list(map(int, os.getenv("ALLOWED_CHAT_IDS").split(',')))
    return (user_id in allowed_user_ids) and (chat_id in allowed_chat_ids)

@dp.message(Command("start"))
async def start(message: types.Message):
    if not validate(message.from_user.id,message.chat.id):
        return
    await message.answer("🚀 Бот для управления сервером активирован!")

@dp.message(Command("disk"))
async def disk_usage(message: types.Message):
    if not validate(message.from_user.id,message.chat.id):
        return
    result = subprocess.run(["df", "-h"], capture_output=True, text=True)
    await message.answer(f"<pre>{result.stdout}</pre>", parse_mode="HTML")

@dp.message(Command("service_status"))
async def service_status(message: types.Message):
    parts = message.text.strip().split(maxsplit=1)
    
    # Проверка, пустое ли сообщение
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("❗️ Напишите название сервиса после команды, например:\n<code>/service_status nginx</code>", parse_mode="HTML")
        return

    service_name = parts[1].strip()

    result = subprocess.run(["systemctl", "status", service_name], capture_output=True, text=True)
    await message.answer(f"<code>{result.stdout}</code>", parse_mode="HTML")

if __name__ == "__main__":
    dp.run_polling(bot)
