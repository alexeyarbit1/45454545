# FIXED VERSION OF THE BOT

import asyncio
import json
import logging
import os
import re
import shutil
import zipfile
import traceback
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from playwright.async_api import async_playwright, Page

BOT_TOKEN = os.getenv("8686276466:AAEYgo-bdiu5nmbdtE6Gcyjo0JVK9AbL7BY")  # <-- SET YOUR TOKEN IN ENV
TARGET_URL = "https://web.max.ru"
QR_SELECTOR = "div.qr, .qr-container, div[data-testid='qr-code']"

PROXY_SERVER = "http://140.233.186.103:46132"
PROXY_USERNAME = "6BSASSEA"
PROXY_PASSWORD = "PRQ3FI8X"

BASE_DATA_DIR = Path("user_data")
BASE_DATA_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

user_sessions = {}
user_locks = {}

def get_accounts_dir(user_id: int) -> Path:
    p = BASE_DATA_DIR / str(user_id) / "accounts"
    p.mkdir(parents=True, exist_ok=True)
    return p

async def close_user_session(user_id: int):
    session = user_sessions.pop(user_id, None)
    if session:
        try:
            await session["browser"].close()
        except Exception as e:
            logging.error(f"Close error: {e}")

async def extract_account_data(page: Page):
    try:
        await asyncio.sleep(2)
        local_storage = await page.evaluate("() => JSON.stringify(localStorage)")
        return {"data": local_storage}
    except Exception as e:
        logging.error(e)
        return None

async def monitor_single_login(page, index, message):
    try:
        await page.wait_for_selector("canvas, svg", state="detached", timeout=60000)
        await message.answer(f"✅ Аккаунт {index} вошёл")

        return await extract_account_data(page)

    except Exception as e:
        logging.error(f"Login error: {e}")
        return None

async def multi_login_process(user_id, message, count):
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()

    if user_locks[user_id].locked():
        await message.answer("⚠️ Уже выполняется процесс")
        return

    async with user_locks[user_id]:
        try:
            async with async_playwright() as p:

                browser = await p.chromium.launch(
                    headless=False,
                    proxy={
                        "server": PROXY_SERVER,
                        "username": PROXY_USERNAME,
                        "password": PROXY_PASSWORD
                    }
                )

                user_sessions[user_id] = {"browser": browser}
                tasks = []

                for i in range(1, count + 1):
                    context = await browser.new_context()
                    page = await context.new_page()

                    await page.goto(TARGET_URL)

                    qr = page.locator(QR_SELECTOR)

                    if await qr.count() == 0:
                        qr = page.locator("svg").first

                    await qr.wait_for()

                    file_name = f"qr_{user_id}_{i}.jpg"
                    with open(file_name, "wb") as f:
                        f.write(await qr.screenshot())

                    await message.answer_photo(FSInputFile(file_name))

                    tasks.append(monitor_single_login(page, i, message))

                results = await asyncio.gather(*tasks, return_exceptions=True)

                valid = []
                for r in results:
                    if isinstance(r, Exception):
                        logging.error(r)
                    elif r:
                        valid.append(r)

                await message.answer(f"Готово: {len(valid)} аккаунтов")

        except Exception:
            logging.error(traceback.format_exc())
            await message.answer("❌ Критическая ошибка")

        finally:
            await close_user_session(user_id)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Запуск")

@dp.message(F.text == "login")
async def login(message: types.Message):
    await multi_login_process(message.from_user.id, message, 1)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
