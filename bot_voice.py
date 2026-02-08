
import asyncio
import os
import logging
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, Application
from aiohttp import web
from dotenv import load_dotenv

import speech_recognition as sr
from pydub import AudioSegment

# Новая библиотека Google GenAI
from google import genai
from google.genai import types

# Загрузка переменных
load_dotenv()
TOKEN_VOICE = os.getenv("TOKEN_VOICE")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "https://your-app.onrender.com")
PORT = int(os.getenv("PORT", 10000))

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация клиента Google GenAI
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("[Gemini] Client initialized successfully.")
    except Exception as e:
        logger.error(f"[Gemini Error] Initialization failed: {e}")
else:
    logger.warning("[WARNING] GEMINI_API_KEY not found!")

# ===== UTILS =====

async def recognize_gemini(file_path):
    """Распознавание через новый Gemini API (v2 Client)."""
    if not client:
        return None, None

    try:
        # Читаем файл байтами
        with open(file_path, "rb") as f:
            audio_bytes = f.read()

        # Определяем MIME
        file_str = str(file_path).lower()
        mime_type = "audio/ogg" 
        if file_str.endswith(".mp3"):
            mime_type = "audio/mp3"
        elif file_str.endswith(".wav"):
            mime_type = "audio/wav"

        prompt = "Transcribe this audio exactly as spoken. Punctuated properly. Do not add any other text."
        
        # Список моделей для перебора
        models_to_try = ["gemini-1.5-flash", "gemini-1.5-flash-001", "gemini-1.5-pro"]
        
        last_error = None
        for model_name in models_to_try:
            try:
                # logger.info(f"Attempting {model_name}...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
                    ]
                )
                text = response.text.strip() if response.text else ""
                return text, "detected"
            except Exception as e:
                # logger.warning(f"{model_name} failed: {e}")
                last_error = e
                continue
        
        # Если ни одна модель не справилась
        if last_error:
            logger.error(f"[Gemini All Models Failed] Last: {last_error}")
        return None, None

    except Exception as e:
        logger.error(f"[Gemini Global Error] {e}")
        return None, None

def recognize_google(wav_path, lang="ru-RU"):
    """Старый добрый Google Speech"""
    r = sr.Recognizer()
    try:
        with sr.AudioFile(str(wav_path)) as source:
            audio = r.record(source)
        return r.recognize_google(audio, language=lang)
    except:
        return None

async def recognize_speech(file_path, wav_path):
    """Диспетчер распознавания"""
    # 1. Gemini
    if client:
        logger.info(f"Trying Gemini for {file_path}")
        text, lang = await recognize_gemini(file_path)
        if text:
            return text, "gemini"
    
    # 2. Google Fallback
    logger.info("Fallback to Google Legacy")
    loop = asyncio.get_running_loop()
    
    text = await loop.run_in_executor(None, recognize_google, wav_path, "ru-RU") 
    if text:
        return text, "google"
        
    text = await loop.run_in_executor(None, recognize_google, wav_path, "en-US")
    if text:
        return text, "google"
        
    return None, None

def add_punctuation(text):
    if not text: return text
    t = text.capitalize()
    if not t.endswith((".", "!", "?")): t += "."
    return t

# ===== BOT LOGIC =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Voice Bot V2 (New Lib) ready!\nSend me voice messages.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = await update.message.reply_text("🎧 Listening...")
    try:
        voice = update.message.voice or update.message.audio or update.message.video_note or update.message.document
        if not voice: return

        file_id = voice.file_id
        new_file = await context.bot.get_file(file_id)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Determine extension
            ext = ".oga"
            if update.message.audio: ext = ".mp3"
            elif update.message.video_note: ext = ".mp4"
            
            input_path = temp_path / f"voice{ext}"
            wav_path = temp_path / "audio.wav"
            
            await new_file.download_to_drive(input_path)
            
            # Convert to WAV (always needed for fallback)
            # Use pydub to convert input to wav
            sound = AudioSegment.from_file(str(input_path))
            sound.export(str(wav_path), format="wav")
            
            text, engine = await recognize_speech(input_path, wav_path)
            
            if text:
                # Format response
                if engine == "google":
                    text = add_punctuation(text)
                
                resp = f"🗣 <b>{text}</b>"
                if engine == "gemini":
                    resp += "\n\n✨ Gemini (HQ)"
                
                await status.edit_text(resp, parse_mode="HTML")
            else:
                await status.edit_text("❌ Could not recognize speech.")

    except Exception as e:
        logger.error(f"Error handling voice: {e}")
        await status.edit_text(f"⚠️ Error: {str(e)}")

# ===== WEB SERVER =====

async def telegram_webhook(request):
    """Handle incoming Telegram updates via Webhook"""
    bot_app = request.app['bot_app']
    try:
        data = await request.json()
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(text="Error", status=500)


def init_app():
    """Initialize Aiohttp App with Bot context (Sync wrapper)"""
    # 1. Bot App (Sync builder part)
    builder = ApplicationBuilder().token(TOKEN_VOICE)
    application = builder.build()
    
    # Handlers
    application.add_handler(MessageHandler(filters.COMMAND, start))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE | filters.Document.AUDIO, handle_voice))
    
    # 2. Web App
    app = web.Application()
    app['bot_app'] = application
    
    # Routes
    webhook_path = f"/webhook/{TOKEN_VOICE}"
    
    async def webhook_handler(request):
        try:
            bot_app = request.app['bot_app']
            data = await request.json()
            update = Update.de_json(data, bot_app.bot)
            await bot_app.process_update(update)
            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return web.Response(text="Error", status=500)

    app.router.add_post(webhook_path, webhook_handler)
    app.router.add_get("/", lambda r: web.Response(text="Bot is running"))
    app.router.add_get("/health", lambda r: web.Response(text="OK"))

    # Lifecycle
    async def on_startup(app):
        webhook_url = f"{RENDER_EXTERNAL_URL}{webhook_path}"
        logger.info(f"Setting webhook to: {webhook_url}")
        await application.bot.set_webhook(webhook_url)
        await application.initialize()
        await application.start()

    async def on_shutdown(app):
        await application.stop()
        await application.shutdown()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_shutdown)
    
    return app

if __name__ == "__main__":
    # Start web server
    logging.basicConfig(level=logging.INFO)
    app = init_app()
    web.run_app(app, port=PORT)
