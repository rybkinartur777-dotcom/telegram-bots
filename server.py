"""
Единый сервер для Render.com
- Voice Bot (Voxify): webhook через aiohttp
- Media Bot (SaveForge): polling в отдельном потоке
"""

import asyncio
import os
import logging
import tempfile
import threading
import urllib.request
import subprocess
import shutil
from pathlib import Path

from aiohttp import web
from dotenv import load_dotenv

# Voice Bot
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters, Application
import speech_recognition as sr
from pydub import AudioSegment
from google import genai
from google.genai import types

# Media Bot
from aiogram import Bot as AiogramBot, Dispatcher as AiogramDispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message as AiogramMessage, FSInputFile, InputMediaPhoto
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from yt_dlp import YoutubeDL

# ===== CONFIG =====
load_dotenv()
TOKEN_VOICE = os.getenv("TOKEN_VOICE")
TOKEN_MEDIA = os.getenv("TOKEN_MEDIA")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "")
PORT = int(os.getenv("PORT", 10000))
MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024

logging.basicConfig(
    format='%(asctime)s [%(name)s] %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("server")

# ===== GEMINI =====
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("[Gemini] OK")
    except Exception as e:
        logger.error(f"[Gemini] Init failed: {e}")


# ========================================
#  VOICE BOT (python-telegram-bot + webhook)
# ========================================

async def recognize_gemini(file_path, mime_type):
    if not gemini_client:
        return None
    try:
        with open(file_path, "rb") as f:
            audio_bytes = f.read()
        if not audio_bytes:
            return None

        prompt = (
            "Транскрибируй это аудио/видео на русском языке дословно. "
            "Добавь правильную пунктуацию. "
            "Верни ТОЛЬКО текст, без пояснений."
        )
        models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        for model_name in models:
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
                    ]
                )
                text = response.text.strip() if response.text else ""
                if text:
                    logger.info(f"[Gemini] OK: {model_name}")
                    return text
            except Exception as e:
                logger.warning(f"[Gemini] {model_name}: {e}")
                continue
        return None
    except Exception as e:
        logger.error(f"[Gemini] Error: {e}")
        return None


def recognize_google_sr(wav_path, lang="ru-RU"):
    r = sr.Recognizer()
    try:
        with sr.AudioFile(str(wav_path)) as source:
            audio = r.record(source)
        return r.recognize_google(audio, language=lang)
    except:
        return None


def get_voice_mime(message):
    if message.video_note:
        return "video/mp4"
    elif message.audio:
        return getattr(message.audio, 'mime_type', "audio/mpeg") or "audio/mpeg"
    elif message.voice:
        return "audio/ogg"
    elif message.document:
        return getattr(message.document, 'mime_type', "audio/mpeg") or "audio/mpeg"
    return "audio/ogg"


async def voice_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎙️ <b>Voxify — Голосовой бот</b>\n\n"
        "Отправь голосовое, аудио или видеокружок!",
        parse_mode="HTML"
    )


async def voice_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = await update.message.reply_text("🎧 Обрабатываю...")
    try:
        msg = update.message
        if msg.voice:
            voice_obj, ext = msg.voice, ".ogg"
        elif msg.audio:
            voice_obj, ext = msg.audio, ".mp3"
        elif msg.video_note:
            voice_obj, ext = msg.video_note, ".mp4"
        elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith("audio"):
            voice_obj, ext = msg.document, ".mp3"
        else:
            await status.edit_text("❌ Не найден аудиофайл.")
            return

        mime_type = get_voice_mime(msg)
        new_file = await context.bot.get_file(voice_obj.file_id)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / f"voice{ext}"
            wav_path = temp_path / "audio.wav"

            await new_file.download_to_drive(input_path)
            logger.info(f"[Voice] Downloaded {input_path.stat().st_size} bytes, mime={mime_type}")

            # 1. Gemini
            text = await recognize_gemini(input_path, mime_type)
            engine = "gemini" if text else None

            # 2. Fallback — Google Speech
            if not text:
                try:
                    sound = AudioSegment.from_file(str(input_path))
                    sound.set_frame_rate(16000).set_channels(1).export(str(wav_path), format="wav")
                    loop = asyncio.get_running_loop()
                    text = await loop.run_in_executor(None, recognize_google_sr, wav_path)
                    if text:
                        engine = "google"
                except Exception as e:
                    logger.warning(f"[Fallback] {e}")

            if text:
                label = "✨ Gemini" if engine == "gemini" else "🔤 Google"
                await status.edit_text(f"🗣 <b>{text}</b>\n\n<i>{label}</i>", parse_mode="HTML")
            else:
                await status.edit_text("❌ Не удалось распознать речь.")

    except Exception as e:
        logger.error(f"[Voice] Error: {e}", exc_info=True)
        await status.edit_text(f"⚠️ Ошибка: {str(e)}")


# ========================================
#  MEDIA BOT (aiogram + polling)
# ========================================

media_dp = AiogramDispatcher()


@media_dp.message(CommandStart())
async def media_start(message: AiogramMessage):
    await message.answer(
        "🌐 <b>SaveForge — Media Bot</b>\n\n"
        "Кинь ссылку с Instagram, TikTok или Pinterest!"
    )


@media_dp.message(lambda m: m.text and ('http://' in m.text or 'https://' in m.text))
async def media_handle(message: AiogramMessage):
    allowed = ['instagram.com', 'www.instagram.com', 'pinterest.com',
               'www.pinterest.com', 'pin.it', 'tiktok.com', 'www.tiktok.com', 'vt.tiktok.com']

    url = message.text.strip()
    if not any(d in url.lower() for d in allowed):
        return

    status_msg = await message.reply("⏳ Скачиваю...")

    try:
        with tempfile.TemporaryDirectory() as tmpdirname:
            media_group = []

            if 'pin.it' in url or 'pinterest' in url.lower():
                ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                images = info.get('images', [])
                if not images:
                    await status_msg.edit_text("❌ Не нашёл фото.")
                    return
                for i, img in enumerate(images[:10]):
                    img_url = img.get('url') or img.get('src') or img.get('original')
                    if not img_url:
                        continue
                    filename = os.path.join(tmpdirname, f"pin_{i}.jpg")
                    urllib.request.urlretrieve(img_url, filename)
                    media_group.append(InputMediaPhoto(media=FSInputFile(filename)))
            else:
                ydl_opts = {
                    'quiet': True, 'no_warnings': True,
                    'outtmpl': os.path.join(tmpdirname, '%(id)s.%(ext)s'),
                    'format': 'bestvideo+bestaudio/best',
                    'merge_output_format': 'mp4',
                }
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                for file in os.listdir(tmpdirname):
                    file_path = os.path.join(tmpdirname, file)
                    if file.lower().endswith(('.mp4', '.webm', '.mov')):
                        size = os.path.getsize(file_path)
                        if size <= MAX_VIDEO_SIZE_BYTES:
                            await message.answer_video(video=FSInputFile(file_path), supports_streaming=True)
                        else:
                            await message.answer_document(document=FSInputFile(file_path))
                        await status_msg.delete()
                        return
                    else:
                        media_group.append(InputMediaPhoto(media=FSInputFile(file_path)))

            if not media_group:
                await status_msg.edit_text("❌ Медиа не найдено.")
                return

            if len(media_group) == 1:
                await message.answer_photo(photo=media_group[0].media)
            else:
                await message.answer_media_group(media=media_group)
            await status_msg.delete()

    except Exception as e:
        logger.error(f"[Media] {e}", exc_info=True)
        try:
            await status_msg.edit_text(f"❌ Ошибка: {str(e)}")
        except:
            await message.reply(f"❌ Ошибка: {str(e)}")


def run_media_bot():
    """Запускает Media Bot polling в отдельном event loop / потоке"""
    async def _run():
        bot = AiogramBot(token=TOKEN_MEDIA, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("[Media Bot] Webhook сброшен, polling...")
        await media_dp.start_polling(bot)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_run())


# ========================================
#  WEB SERVER (aiohttp) + запуск обоих ботов
# ========================================

def create_app():
    """Создаёт aiohttp приложение с Voice Bot webhook"""

    voice_app = (
        ApplicationBuilder()
        .token(TOKEN_VOICE)
        .build()
    )
    voice_app.add_handler(CommandHandler("start", voice_start))
    voice_app.add_handler(MessageHandler(
        filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE | filters.Document.AUDIO,
        voice_handle
    ))

    app = web.Application()
    app['voice_app'] = voice_app

    webhook_path = f"/webhook/{TOKEN_VOICE}"

    async def webhook_handler(request):
        try:
            va = request.app['voice_app']
            data = await request.json()
            update = Update.de_json(data, va.bot)
            await va.process_update(update)
            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"[Webhook] {e}")
            return web.Response(text="Error", status=500)

    app.router.add_post(webhook_path, webhook_handler)
    app.router.add_get("/", lambda r: web.Response(text="Bots are running!"))
    app.router.add_get("/health", lambda r: web.Response(text="OK"))

    async def on_startup(app):
        va = app['voice_app']
        await va.initialize()
        await va.start()

        webhook_url = f"{RENDER_EXTERNAL_URL}{webhook_path}"
        await va.bot.set_webhook(webhook_url)
        logger.info(f"[Voice Bot] Webhook set: {webhook_url}")

        # Запускаем Media Bot в отдельном потоке
        t = threading.Thread(target=run_media_bot, daemon=True)
        t.start()
        logger.info("[Media Bot] Started in background thread")

    async def on_shutdown(app):
        va = app['voice_app']
        await va.stop()
        await va.shutdown()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_shutdown)

    return app


if __name__ == "__main__":
    if not TOKEN_VOICE or not TOKEN_MEDIA:
        logger.error("TOKEN_VOICE and TOKEN_MEDIA must be set in .env!")
        exit(1)

    logger.info(f"Starting server on port {PORT}...")
    app = create_app()
    web.run_app(app, port=PORT)
