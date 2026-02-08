import asyncio
import os
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()

async def delete_webhook():
    bot = Bot(token=os.getenv("TOKEN_MEDIA"))
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Webhook deleted! Now you can run bot_media_local.py")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(delete_webhook())
