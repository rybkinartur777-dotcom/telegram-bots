import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from dotenv import load_dotenv
import yt_dlp

load_dotenv()

TOKEN_MEDIA = os.getenv("TOKEN_MEDIA")
if not TOKEN_MEDIA:
    raise ValueError("TOKEN_MEDIA not found in .env file!")

bot = Bot(token=TOKEN_MEDIA)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.reply(
        "👋 Привет! Я бот для скачивания медиа.\n\n"
        "Отправь мне ссылку на:\n"
        "• TikTok\n"
        "• Instagram\n"
        "• Pinterest\n\n"
        "Я скачаю и пришлю тебе видео/фото!"
    )

@dp.message(lambda message: message.text and ("http://" in message.text or "https://" in message.text))
async def handle_link(message: types.Message):
    text = message.text
    
    status_msg = await message.reply("⏳ Скачиваю...")
    
    try:
        # yt-dlp options
        ydl_opts = {
            'format': 'best',
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(text, download=True)
            filename = ydl.prepare_filename(info)
            
            await status_msg.edit_text("📤 Отправляю...")
            
            # Отправляем файл используя FSInputFile
            video_file = FSInputFile(filename)
            await message.answer_video(video_file)
            
            # Удаляем файл
            os.remove(filename)
            await status_msg.delete()
            
    except Exception as e:
        error_text = f"❌ Ошибка: {str(e)}\n\nПопробуйте другую ссылку."
        await status_msg.edit_text(error_text)
        logging.error(f"Error: {e}")

async def main():
    print("[MEDIA BOT LOCAL] Started in POLLING mode!")
    print("Press Ctrl+C to stop")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
