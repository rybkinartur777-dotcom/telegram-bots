# Force redeploy trigger (new library migration V2)
import asyncio
import os
import tempfile
import logging
import re
from pathlib import Path

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

import speech_recognition as sr
from pydub import AudioSegment, effects, silence 

# Новая библиотека Google GenAI
from google import genai
from google.genai import types

# Загружаем переменные окружения из .env файла
load_dotenv()

TOKEN_VOICE = os.getenv("TOKEN_VOICE")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Инициализация клиента (новая библиотека)
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
#         print("[Gemini] Client initialized successfully.")
    except Exception as e:
        print(f"[Gemini Error] Initialization failed: {e}")
else:
    print("[WARNING] GEMINI_API_KEY not found! High quality recognition disabled.")


# ===== FFMPEG SETUP =====
FFMPEG_PATH = None
if os.name == 'nt':
    local_ffmpeg = os.path.join(os.path.dirname(__file__), "ffmpeg", "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        FFMPEG_PATH = local_ffmpeg
else:
    FFMPEG_PATH = shutil.which("ffmpeg")

if FFMPEG_PATH:
    print(f"[FFmpeg] Using: {FFMPEG_PATH}")
    # Для pydub и speech_recognition настройки
    AudioSegment.converter = FFMPEG_PATH
    AudioSegment.ffmpeg = FFMPEG_PATH
    AudioSegment.ffprobe = FFMPEG_PATH
else:
    print("[WARNING] FFmpeg not found! Voice processing might fail.")


# ===== UTILS =====
TRANSLIT_DICT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
    'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': "'", 'э': 'e', 'ю': 'yu',
    'я': 'ya',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh',
    'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O',
    'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'H', 'Ц': 'Ts',
    'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch', 'Ъ': '"', 'Ы': 'Y', 'Ь': "'", 'Э': 'E', 'Ю': 'Yu',
    'Я': 'Ya'
}

def transliterate(text):
    if not text: return ""
    result = []
    for char in text:
        result.append(TRANSLIT_DICT.get(char, char))
    return "".join(result)

def add_punctuation(text):
    """
    Простая эвристика для пунктуации, так как нейросети тяжелые.
    """
    if not text: return ""
    
    # Capitalize first letter
    text = text[0].upper() + text[1:]
    
    # Add dot at end if missing
    if text[-1] not in ".!?":
        text += "."
        
    return text

def convert_to_wav(input_file, output_file):
    """Convert any audio to WAV 16000Hz mono using ffmpeg"""
    try:
        command = [
            FFMPEG_PATH if FFMPEG_PATH else "ffmpeg",
            "-y",
            "-i", input_file,
            "-ar", "16000",
            "-ac", "1",
            output_file
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"[FFmpeg Error] {e}")
        return False

async def download_with_retries(file_obj, dest_path, attempts=3, delay=0.12):
    for i in range(attempts):
        try:
            await bot.download(file_obj, destination=dest_path)
            return True
        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            print(f"[Telegram] Rate limit hit. Waiting {wait_time}s...")
            await asyncio.sleep(wait_time)
        except Exception as e:
            print(f"[Download Error] Attempt {i+1}/{attempts}: {e}")
            await asyncio.sleep(delay)
    return False


# ===== GOOGLE SPEECH =====

# ===== RECOGNITION =====

def recognize_gemini(file_path):
    """
    Распознавание через Google Gemini (Бесплатно, качественно, с пунктуацией)
    """
    Распознавание через новый Gemini API (v2 Client).
    """
    if not client:
        return None, None

    try:
        # Читаем файл как байты
        with open(file_path, "rb") as f:
            audio_data = f.read()

        # Новый формат запроса (Part с MIME типом)
        # Для ogg (voice note) используем audio/ogg
        mime_type = "audio/ogg" 
        if file_path.endswith(".mp3"):
            mime_type = "audio/mp3"
        elif file_path.endswith(".wav"):
            mime_type = "audio/wav"

        # Формируем контент
        prompt = "Transcribe this audio exactly as spoken. Punctuated properly. Do not add any other text."
        
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[prompt, types.Part.from_bytes(data=audio_data, mime_type=mime_type)]
        )
        
        text = response.text.strip() if response.text else ""
        lang = "detected" 
        
        return text, lang
            
    except Exception as e:
        print(f"[Gemini Error] {e}")
        return None, None

def recognize_google(wav_path, lang="ru-RU"):
    """
    Fallback: Google Speech Recognition (Old API)
    """
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    
    with sr.AudioFile(wav_path) as source:
        audio_data = recognizer.record(source)
        
    try:
        text = recognizer.recognize_google(audio_data, language=lang)
        return text
    except sr.UnknownValueError:
        return None
    except Exception as e:
        print(f"[Google Error] {e}")
        return None

def recognize_speech(file_path, wav_path):
    """
    Умный выбор движка:
    1. Gemini (HQ, пунктуация, бесплатно)
    2. Google Speech (Legacy, запасной вариант)
    """
    # 1. Пробуем Gemini (если есть ключ)
    if client:
        print("[Speech] Trying Gemini v2...")
        text, lang = recognize_gemini(file_path) # Для войсов (.oga) Gemini понимает
        if text:
            return text, lang, "gemini"
        # Если Gemini вернул None (ошибка), идем дальше...2. Fallback to Google Legacy
    print("[Speech] Fallback to Google Legacy...")
    
    # Try Russian first
    text = recognize_google(wav_path, "ru-RU")
    if text:
        return text, "ru", "google"
        
    # Try English
    text = recognize_google(wav_path, "en-US")
    if text:
        return text, "en", "google"
        
    return None, None, None


# ===== BOT =====
bot = Bot(token=TOKEN_VOICE, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Voice Bot ready!\nSend me voice messages, audio files, or video notes.")

@dp.message()
async def handle_message(message: Message):
    """Handle voice messages, audio files, and video notes"""
    
    try:
        if message.voice:
            file_id = message.voice.file_id
            duration = message.voice.duration
            file_type = "voice"
        elif message.audio:
            file_id = message.audio.file_id
            duration = message.audio.duration
            file_type = "audio"
        elif message.video_note:
            file_id = message.video_note.file_id
            duration = message.video_note.duration
            file_type = "video_note"
        else:
            return  # Not interested

        if duration and duration > 300: # 5 min limit
            await message.reply("Too long! Max 5 minutes.")
            return

        status_msg = await message.reply("🎧 Processing...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 1. Download
            file_info = await bot.get_file(file_id)
            original_ext = os.path.splitext(file_info.file_path)[1] or ".ogg"
            input_path = os.path.join(temp_dir, f"input{original_ext}")
            
            if not await download_with_retries(file_id, input_path):
                await status_msg.edit_text("❌ Failed to download.")
                return

            # 2. Convert to WAV
            wav_path = os.path.join(temp_dir, "audio.wav")
            if not convert_to_wav(input_path, wav_path):
                await status_msg.edit_text("❌ Failed to convert audio.")
                return
                

            # 3. Recognize
            text, lang, engine = recognize_speech(input_path, wav_path)
            
            if text:
                # Gemini adds punctuation automatically
                if engine == "google":
                    text = add_punctuation(text)
                
                response = f"🗣 <b>{text}</b>"
                
                # Add metadata
                footer = []
                if engine == "gemini":
                     footer.append("✨ Gemini (HQ)")
                
                if footer:
                    response += "\n\n" + " | ".join(footer)
                
                await status_msg.edit_text(response)
            else:
                # Если вернулась пустота — значит совсем беда
                await status_msg.edit_text("❌ Не удалось распознать речь (проверьте логи).")
                
    except Exception as e:
        print(f"[Error] {e}")
        try:
            await message.reply("Error processing voice.")
        except:
            pass


if __name__ == "__main__":
    async def main():
        from aiohttp import web
        
        print("[VOICE BOT] Starting webhook setup...")
        
        # Webhook settings
        WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL", "https://your-app.onrender.com")
        WEBHOOK_PATH = f"/webhook/{TOKEN_VOICE}"
        WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
        
        # Web app setup
        app = web.Application()
        
        async def handle_webhook(request):
            """Handle incoming webhook requests"""
            try:
                # print("[WEBHOOK] Received request")
                update_data = await request.json()
                
                from aiogram.types import Update
                update = Update(**update_data)
                
                # Run in background task to not block webhook response
                asyncio.create_task(dp.feed_webhook_update(bot, update))
                
                return web.Response(text="OK")
            except Exception as e:
                print(f"[WEBHOOK ERROR] {e}")
                import traceback
                traceback.print_exc()
                return web.Response(status=500)
        
        app.router.add_post(WEBHOOK_PATH, handle_webhook)
        
        async def health(request):
            return web.Response(text="Voice Bot is running!")
        
        app.router.add_get("/", health)
        app.router.add_get("/health", health)
        
        # Set webhook
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await bot.set_webhook(WEBHOOK_URL)
            print(f"[VOICE BOT] Webhook set to: {WEBHOOK_URL}")
        except Exception as e:
             print(f"[WEBHOOK SET ERROR] {e}")
        
        # Start server
        PORT = int(os.getenv("PORT", 10000))
        print(f"[VOICE BOT] Server starting on port {PORT}...")
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        
        print(f"[VOICE BOT] Server started on port {PORT}")
        
        # Keep running
        await asyncio.Event().wait()

    asyncio.run(main())
