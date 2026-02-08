
import asyncio
import os
import tempfile
import subprocess
import time
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramRetryAfter
import speech_recognition as sr
import shutil
import concurrent.futures
import re
from pydub import AudioSegment, effects, silence
from aiohttp import web
import google.generativeai as genai
import pathlib

# Загружаем переменные окружения из .env файла
load_dotenv()


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

# ===== CONFIG =====
TOKEN_VOICE = os.getenv("TOKEN_VOICE", "YOUR_TOKEN_HERE")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

gemini_model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Используем flash модель так как она быстрая и дешевая (бесплатная в лимитах)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    print("[WARNING] GEMINI_API_KEY not found! High quality recognition disabled.")


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
    if not gemini_model:
        return None, None

    try:
        # Uploading file to Gemini
        # Note: In production you might want to manage file deletion lifecycle better
        # But for this bot standard upload/process is fine
        print(f"[Gemini] Uploading {file_path}...")
        sample_file = genai.upload_file(path=file_path, display_name="Voice Message")
        
        # Poll for processing completion
        while sample_file.state.name == "PROCESSING":
            time.sleep(1)
            sample_file = genai.get_file(sample_file.name)
            
        if sample_file.state.name == "FAILED":
            print("[Gemini] File processing failed.")
            return None, None
            
        # Generate content
        response = gemini_model.generate_content([
            "Transcribe this audio file exactly as spoken. Punctuate properly. Do not add any other text.",
            sample_file
        ])
        
        # Cleanup
        try:
            genai.delete_file(sample_file.name)
        except:
            pass
            
        text = response.text.strip()
        # Simple language detection based on text
        # (Gemini doesn't return language code directly in simple response)
        # We'll assume successful recognition implies valid language
        # You could ask it to output JSON with language, but let's keep it simple
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
    Smart recognition: Try Gemini (Free High Quality) first, then Google (Legacy)
    """
    # 1. Try Gemini (High quality + punctuation + FREE)
    if gemini_model:
        print("[Speech] Trying Gemini...")
        text, lang = recognize_gemini(file_path) # Use original file (ogg/mp3) usually better
        if text:
            return text, lang, "gemini"
            
    # 2. Fallback to Google Legacy
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
            # Pass original input_path for Gemini (it supports ogg/mp3 directly) and wav_path for legacy
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
                await status_msg.edit_text("Could not recognize speech.")
                
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
