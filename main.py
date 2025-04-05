import os
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

SERVICES = ["cron", "ssh", "sysstat", "mysql"]  # Список основных сервисов сервера (для работы команды main_services_status)

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

    if len(parts) < 2 or not parts[1].strip():
        await message.answer("❗️ Напишите название сервиса после команды, например:\n<code>/service_status nginx</code>", parse_mode="HTML")
        return

    service_name = parts[1].strip()

    try:
        result = subprocess.run(
            ["systemctl", "status", service_name],
            capture_output=True,
            text=True,
            check=True  # В случае поломки произойдет исключение
        )
        await message.answer(f"<code>{result.stdout}</code>", parse_mode="HTML")

    except subprocess.CalledProcessError as e:
        # В случае, если указанный сервис не существует:
        error_output = e.stderr or e.stdout or "❌ Не удалось получить статус сервиса."
        await message.answer(f"❗️ Ошибка: <code>{error_output.strip()}</code>", parse_mode="HTML")

@dp.message(Command("ping"))
async def ping_host(message: types.Message):
    parts = message.text.strip().split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer("❗️ Напишите адрес для пинга, например:\n<code>/ping google.com</code>", parse_mode="HTML")
        return

    host = parts[1].strip()

    try:
        result = subprocess.run(
            ["ping", "-c", "4", host],  # Sends 4 ping packets
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            await message.answer(f"<code>{result.stdout}</code>", parse_mode="HTML")
        else:
            await message.answer(f"⚠️ Не удалось допинговать <b>{host}</b>.\n<code>{result.stderr or result.stdout}</code>", parse_mode="HTML")

    except subprocess.TimeoutExpired:
        await message.answer(f"⏱️ Пинг до <b>{host}</b> занял слишком много времени (таймаут).", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка при выполнении пинга: <code>{str(e)}</code>", parse_mode="HTML")

@dp.message(Command("usage"))
async def system_usage(message: types.Message):
    # Get CPU and RAM stats
    cpu_percent = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    ram_used = ram.used / (1024 ** 3)
    ram_total = ram.total / (1024 ** 3)
    ram_percent = ram.percent

    response = (
        f"📊 <b>Системные ресурсы:</b>\n"
        f"🧠 CPU: <b>{cpu_percent}%</b>\n"
        f"💾 RAM: <b>{ram_used:.2f} GB</b> / <b>{ram_total:.2f} GB</b> ({ram_percent}%)"
    )

    await message.answer(response, parse_mode="HTML")

@dp.message(Command("main_services_status"))
async def main_services_status(message: types.Message):
    status_lines = ["📋 <b>Статус сервисов:</b>"]

    for service in SERVICES:
        result = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True,
            text=True
        )
        status = result.stdout.strip()
        if status == "active":
            status_lines.append(f"✅ <b>{service}</b>")
        else:
            status_lines.append(f"❌ <b>{service}</b> ({status})")

    await message.answer("\n".join(status_lines), parse_mode="HTML")

@dp.message(Command("restart_service"))
async def restart_service(message: types.Message):
    parts = message.text.strip().split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer("❗️ Напишите название сервиса после команды, например:\n<code>/restart_service nginx</code>", parse_mode="HTML")
        return

    service_name = parts[1].strip()

    try:
        # Restart the service using systemctl
        result = subprocess.run(
            ["sudo", "systemctl", "restart", service_name],
            capture_output=True,
            text=True
        )

        # Check if the service was restarted successfully
        if result.returncode == 0:
            await message.answer(f"✅ Сервис <b>{service_name}</b> успешно перезапущен!", parse_mode="HTML")
        else:
            await message.answer(f"❌ Не удалось перезапустить сервис <b>{service_name}</b>.\n<code>{result.stderr or result.stdout}</code>", parse_mode="HTML")

    except subprocess.CalledProcessError as e:
        await message.answer(f"❌ Ошибка при перезапуске сервиса: <code>{str(e)}</code>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: <code>{str(e)}</code>", parse_mode="HTML")

if __name__ == "__main__":
    dp.run_polling(bot)
