"""
Единое приложение: и Telegram-бот, и API для мини-аппа, и раздача
статики мини-аппа — всё на одном FastAPI-сервере (удобно для
бесплатного хостинга, где доступен только один публичный порт).
"""

import io
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, Update
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from db import get_groups, get_schedule, init_db, replace_group_schedule
from llm_parser import parse_schedule_image

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "vgatk-secret")
BASE_URL = os.environ["BASE_URL"]  # напр. https://vgatk-bot.onrender.com

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vgatk_bot")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

app = FastAPI()


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    await bot.set_webhook(f"{BASE_URL}/webhook/{WEBHOOK_SECRET}", drop_pending_updates=True)
    log.info("Webhook установлен на %s/webhook/***", BASE_URL)


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Это бот расписания ВГАТК.\n\n"
        "Нажми на кнопку меню слева от поля ввода, чтобы открыть расписание."
    )


@dp.message(F.photo)
async def handle_photo(message: Message) -> None:
    if message.from_user is None or message.from_user.id not in ADMIN_IDS:
        await message.answer("У тебя нет прав загружать расписание.")
        return

    status = await message.answer("Фото получено, распознаю расписание...")

    photo = message.photo[-1]  # берём самое большое разрешение
    file = await bot.get_file(photo.file_id)
    buf = io.BytesIO()
    await bot.download_file(file.file_path, destination=buf)

    try:
        lessons = parse_schedule_image(buf.getvalue())
    except Exception as e:  # noqa: BLE001
        log.exception("Ошибка распознавания")
        await status.edit_text(f"Не получилось распознать расписание: {e}")
        return

    if not lessons:
        await status.edit_text("На фото не удалось найти расписание.")
        return

    groups: dict[str, list[dict]] = {}
    for lesson in lessons:
        groups.setdefault(lesson["group"], []).append(lesson)

    for group, group_lessons in groups.items():
        replace_group_schedule(group, group_lessons)

    await status.edit_text(
        f"Готово! Обновлено групп: {len(groups)} — {', '.join(groups.keys())}."
    )


@app.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request) -> dict:
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="forbidden")
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/api/groups")
async def api_groups() -> JSONResponse:
    return JSONResponse(get_groups())


@app.get("/api/schedule/{group}")
async def api_schedule(group: str) -> JSONResponse:
    return JSONResponse(get_schedule(group))


# Статика мини-аппа — регистрируем ПОСЛЕ роутов API, чтобы /api/* и
# /webhook/* обрабатывались раньше и не перехватывались статикой.
app.mount("/", StaticFiles(directory="miniapp", html=True), name="miniapp")
