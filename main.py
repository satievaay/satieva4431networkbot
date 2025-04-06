import os
import subprocess
import psutil
import hashlib
import tarfile
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Константы
SERVICES = ["cron", "ssh", "sysstat", "mysql"]
AUTH_DURATION = timedelta(hours=1)
SESSIONS = {}  # user_id: expiry_datetime

def is_authenticated(user_id: int) -> bool:
    return user_id in SESSIONS and SESSIONS[user_id] > datetime.now()

def validate(user_id: int, chat_id: int) -> bool:
    # Проверка в ЛС — только авторизация
    if chat_id == user_id:
        return is_authenticated(user_id)
    # В группах — по ID
    allowed_user_ids = list(map(int, os.getenv("ALLOWED_USER_IDS", "").split(',')))
    allowed_chat_ids = list(map(int, os.getenv("ALLOWED_CHAT_IDS", "").split(',')))
    return (user_id in allowed_user_ids) and (chat_id in allowed_chat_ids)

@dp.message(Command("auth"))
async def auth_command(message: types.Message):
    if message.chat.type != "private":
        await message.answer(
        "🔐 Авторизация возможна только в ЛС бота. Перейти в ЛС: "
        "[Написать боту](https://t.me/Satieva4431Bot?start)")
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Введите пароль, например:\n<code>/auth mypassword</code>", parse_mode="HTML")
        return

    input_password = parts[1].strip()
    input_hash = hashlib.md5(input_password.encode()).hexdigest()
    correct_hash = os.getenv("BOT_PASSWORD_HASH")

    if input_hash == correct_hash:
        SESSIONS[message.from_user.id] = datetime.now() + AUTH_DURATION
        await message.answer("✅ Успешная авторизация. Доступ активен на 1 день.")
    else:
        await message.answer("❌ Неверный пароль.")

@dp.message(Command("start"))
async def start(message: types.Message):
    if not validate(message.from_user.id, message.chat.id):
        await message.answer("⛔️ Доступ запрещен.")
        return
    await message.answer("🚀 Бот для управления сервером активирован!")

@dp.message(Command("disk"))
async def disk_usage(message: types.Message):
    if not validate(message.from_user.id, message.chat.id):
        await message.answer("⛔️ Доступ запрещен.")
        return
    result = subprocess.run(["df", "-h"], capture_output=True, text=True)
    await message.answer(f"<pre>{result.stdout}</pre>", parse_mode="HTML")

@dp.message(Command("service_status"))
async def service_status(message: types.Message):
    if not validate(message.from_user.id, message.chat.id):
        await message.answer("⛔️ Доступ запрещен.")
        return
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
    if not validate(message.from_user.id, message.chat.id):
        await message.answer("⛔️ Доступ запрещен.")
        return
    parts = message.text.strip().split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer("❗️ Напишите адрес для пинга, например:\n<code>/ping google.com</code>", parse_mode="HTML")
        return

    host = parts[1].strip()

    try:
        result = subprocess.run(
            ["ping", "-c", "4", host],  # Отправка 4 пакетов ping
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
    if not validate(message.from_user.id, message.chat.id):
        await message.answer("⛔️ Доступ запрещен.")
        return
    # Получить информацию по загруженности процессора и ОЗУ
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
    if not validate(message.from_user.id, message.chat.id):
        await message.answer("⛔️ Доступ запрещен.")
        return
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
    if not validate(message.from_user.id, message.chat.id):
        await message.answer("⛔️ Доступ запрещен.")
        return
    parts = message.text.strip().split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer("❗️ Напишите название сервиса после команды, например:\n<code>/restart_service nginx</code>", parse_mode="HTML")
        return

    service_name = parts[1].strip()

    try:
        # Перезапуск службы с помощью systemctl restart
        result = subprocess.run(
            ["sudo", "systemctl", "restart", service_name],
            capture_output=True,
            text=True
        )

        # Проверка результата перезапуска службы:
        if result.returncode == 0:
            await message.answer(f"✅ Сервис <b>{service_name}</b> успешно перезапущен!", parse_mode="HTML")
        else:
            await message.answer(f"❌ Не удалось перезапустить сервис <b>{service_name}</b>.\n<code>{result.stderr or result.stdout}</code>", parse_mode="HTML")

    except subprocess.CalledProcessError as e:
        await message.answer(f"❌ Ошибка при перезапуске сервиса: <code>{str(e)}</code>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: <code>{str(e)}</code>", parse_mode="HTML")

@dp.message(Command("traceroute"))
async def traceroute(message: types.Message):
    if not validate(message.from_user.id, message.chat.id):
        await message.answer("⛔️ Доступ запрещен.")
        return
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("❗️ Напишите адрес для трассировки, например:\n<code>/traceroute google.com</code>", parse_mode="HTML")
        return

    host = parts[1].strip()

    try:
        result = subprocess.run(
            ["traceroute", host],
            capture_output=True,
            text=True,
            timeout=10
        )
        await message.answer(f"🔍 Трассировка маршрута до <b>{host}</b>:\n<pre>{result.stdout}</pre>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка при трассировке маршрута: <code>{str(e)}</code>", parse_mode="HTML")

@dp.message(Command("backup"))
async def backup_configs(message: types.Message):
    user_id = message.from_user.id
    if not validate(user_id, message.chat.id):
        await message.answer("Доступ запрещен.")
        return

    config_paths = os.getenv("BACKUP_FILES", "").split(",")
    backup_dir = os.getenv("BACKUP_DIR", "/tmp")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"backup_{timestamp}.tar.gz"
    archive_path = os.path.join(backup_dir, archive_name)

    os.makedirs(backup_dir, exist_ok=True)

    try:
        with tarfile.open(archive_path, "w:gz") as archive:
            for path in config_paths:
                path = path.strip()
                if os.path.exists(path):
                    archive.add(path, arcname=os.path.basename(path))
                else:
                    await message.answer(f"⚠️ Файл не найден: {path}")

        await message.answer("✅ Бэкап создан. Архив будет отправлен вам в личные сообщения.")

        try:
            await bot.send_document(user_id, types.FSInputFile(archive_path), caption="📦 Резервная копия конфигурации")
        except aiogram.exceptions.TelegramForbiddenError:
            await message.answer("❗ Не удалось отправить файл в личные сообщения. Убедитесь, что вы начали чат с ботом (нажмите /start в ЛС).")

    except Exception as e:
        await message.answer(f"❌ Ошибка при создании бэкапа: <code>{str(e)}</code>", parse_mode="HTML")

if __name__ == "__main__":
    dp.run_polling(bot)
