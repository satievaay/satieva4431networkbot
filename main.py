import os
import subprocess
import psutil
import hashlib
import tarfile
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
from datetime import datetime, timedelta
import asyncio

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Константы
SERVICES = ["cron", "ssh", "sysstat", "mysql"]
AUTH_DURATION = timedelta(hours=1)
ALLOWED_USER_IDS = list(map(int, os.getenv("ALLOWED_USER_IDS", "").split(',')))  # Загрузка разрешенных пользователей из .env
SESSIONS = {}  # user_id: expiry_datetime
MONITORING_INTERVAL = 300  # 5 минут в секундах
MONITORING_USERS = set()  # Пользователи, получающие мониторинг

def is_authenticated(user_id: int) -> bool:
    """Проверка, авторизован ли пользователь."""
    return user_id in SESSIONS and SESSIONS[user_id] > datetime.now()

def validate(user_id: int) -> bool:
    """Проверка, авторизован ли пользователь (независимо от чата)."""
    return user_id in ALLOWED_USER_IDS and is_authenticated(user_id)

@dp.message(Command("auth"))
async def auth_command(message: types.Message):
    if message.chat.type != "private":
        await message.answer(
        "🔐 Авторизация возможна только в ЛС бота. Перейти в ЛС: "
        '<a href="https://t.me/Satieva4431Bot?start">Написать боту</a>',
        parse_mode="HTML")
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Введите пароль, например:\n<code>/auth mypassword</code>", parse_mode="HTML")
        return

    input_password = parts[1].strip()
    input_hash = hashlib.md5(input_password.encode()).hexdigest()
    correct_hash = os.getenv("BOT_PASSWORD")
    if message.from_user.id not in ALLOWED_USER_IDS:
        await message.answer("⛔️ Доступ запрещен.")
        return
    if input_hash == correct_hash:
        SESSIONS[message.from_user.id] = datetime.now() + AUTH_DURATION
        await message.answer("✅ Успешная авторизация. Доступ активен на 1 час.")
    else:
        await message.answer("❌ Неверный пароль.")

@dp.message(Command("start"))
async def start(message: types.Message):
    if (message.from_user.id not in ALLOWED_USER_IDS):
        await message.answer("⛔️ Доступ запрещен.")
        return
    await message.answer("🚀 Бот для управления сервером активирован!")

@dp.message(Command("disk"))
async def disk_usage(message: types.Message):
    if not validate(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен. Для авторизации напишите /auth.")
        return
    result = subprocess.run(["df", "-h"], capture_output=True, text=True)
    await message.answer(f"<pre>{result.stdout}</pre>", parse_mode="HTML")

@dp.message(Command("service_status"))
async def service_status(message: types.Message):
    if not validate(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен. Для авторизации напишите /auth.")
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
    if not validate(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен. Для авторизации напишите /auth.")
        return
    parts = message.text.strip().split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer("❗️ Напишите адрес для пинга, например:\n<code>/ping google.com</code>", parse_mode="HTML")
        return

    host = parts[1].strip()

    try:
        result = subprocess.run(
            ["ping", "-c", "4", host],
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
    if not validate(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен. Для авторизации напишите /auth.")
        return
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
    if not validate(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен. Для авторизации напишите /auth.")
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
    if not validate(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен. Для авторизации напишите /auth.")
        return
    parts = message.text.strip().split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer("❗️ Напишите название сервиса после команды, например:\n<code>/restart_service nginx</code>", parse_mode="HTML")
        return

    service_name = parts[1].strip()

    try:
        result = subprocess.run(
            ["sudo", "systemctl", "restart", service_name],
            capture_output=True,
            text=True
        )

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
    if not validate(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен. Для авторизации напишите /auth.")
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
    if not validate(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен. Для авторизации напишите /auth.")
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

async def send_monitoring_data(user_id: int):
    """Отправляет данные мониторинга пользователю."""
    try:
        # Отправляем данные диска
        disk_result = subprocess.run(["df", "-h"], capture_output=True, text=True)
        await bot.send_message(user_id, f"<b>🔄 Автоматический мониторинг (диск):</b>\n<pre>{disk_result.stdout}</pre>", parse_mode="HTML")
        
        # Отправляем данные использования системы
        cpu_percent = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        ram_used = ram.used / (1024 ** 3)
        ram_total = ram.total / (1024 ** 3)
        ram_percent = ram.percent

        usage_message = (
            f"<b>🔄 Автоматический мониторинг (ресурсы):</b>\n"
            f"🧠 CPU: <b>{cpu_percent}%</b>\n"
            f"💾 RAM: <b>{ram_used:.2f} GB</b> / <b>{ram_total:.2f} GB</b> ({ram_percent}%)"
        )
        await bot.send_message(user_id, usage_message, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка при отправке мониторинга пользователю {user_id}: {e}")

async def monitoring_task():
    """Фоновая задача для периодической отправки мониторинга."""
    while True:
        await asyncio.sleep(MONITORING_INTERVAL)
        for user_id in list(MONITORING_USERS):
            if validate(user_id):
                await send_monitoring_data(user_id)
            else:
                MONITORING_USERS.discard(user_id)

@dp.message(Command("monitor_start"))
async def start_monitoring(message: types.Message):
    """Включение периодического мониторинга."""
    if not validate(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен. Для авторизации напишите /auth.")
        return
    
    MONITORING_USERS.add(message.from_user.id)
    await message.answer("✅ Автоматический мониторинг включен. Вы будете получать данные каждые 5 минут.")

@dp.message(Command("monitor_stop"))
async def stop_monitoring(message: types.Message):
    """Выключение периодического мониторинга."""
    if message.from_user.id in MONITORING_USERS:
        MONITORING_USERS.discard(message.from_user.id)
        await message.answer("⏹ Автоматический мониторинг отключен.")
    else:
        await message.answer("ℹ️ Автоматический мониторинг уже отключен.")

async def on_startup(dp):
    """Действия при запуске бота."""
    asyncio.create_task(monitoring_task())

if __name__ == "__main__":
    dp.startup.register(on_startup)
    dp.run_polling(bot)
