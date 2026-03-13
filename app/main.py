import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.config import BOT_TOKEN
from app.services.database import init_db
from app.handlers.general import router as general_router
from app.handlers.admin import router as admin_router
from app.handlers.moderation import router as moderation_router

logging.basicConfig(level=logging.INFO)


async def main():
    if not BOT_TOKEN:
        raise ValueError("Falta BOT_TOKEN en el archivo .env")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(general_router)
    dp.include_router(admin_router)
    dp.include_router(moderation_router)

    await init_db()

    print("Bot iniciado correctamente...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())