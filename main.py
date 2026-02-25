"""
main.py — Запускает ОБА бота параллельно (polling режим)
Используется для деплоя на Railway.app
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger("launcher")

# ===================== VOICE BOT =====================

async def run_voice_bot():
    """Голосовой бот на python-telegram-bot (polling)"""
    import tempfile
    from pathlib import Path
    from telegram import Update
    from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters, Application
    from pydub import AudioSegment
    import speech_recognition as sr
    from google import genai
    from google.genai import types

    TOKEN_VOICE = os.getenv("TOKEN_VOICE")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    if not TOKEN_VOICE:
        logger.error("[VoiceBot] TOKEN_VOICE не задан! Бот не запустится.")
        return

    voice_logger = logging.getLogger("voice_bot")

    # Gemini клиент
    gemini_client = None
    if GEMINI_API_KEY:
        try:
            gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            voice_logger.info("Gemini client OK")
        except Exception as e:
            voice_logger.error(f"Gemini init error: {e}")

    def get_mime_type(msg):
        if msg.video_note:
            return "video/mp4"
        elif msg.audio:
            return getattr(msg.audio, 'mime_type', None) or "audio/mpeg"
        elif msg.voice:
            return "audio/ogg"
        elif msg.document:
            return getattr(msg.document, 'mime_type', None) or "audio/mpeg"
        return "audio/ogg"

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
                "Добавь правильную пунктуацию (запятые, точки, знаки вопроса). "
                "Верни ТОЛЬКО текст транскрипции, без пояснений и комментариев."
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
                        voice_logger.info(f"Gemini OK [{model_name}]: {text[:60]}")
                        return text
                except Exception as e:
                    voice_logger.warning(f"Gemini {model_name} failed: {e}")
            return None
        except Exception as e:
            voice_logger.error(f"Gemini error: {e}")
            return None

    def recognize_google_sr(wav_path, lang="ru-RU"):
        r = sr.Recognizer()
        try:
            with sr.AudioFile(str(wav_path)) as source:
                audio = r.record(source)
            return r.recognize_google(audio, language=lang)
        except sr.UnknownValueError:
            return None
        except Exception as e:
            voice_logger.warning(f"Google SR error: {e}")
            return None

    def convert_to_wav(input_path, wav_path):
        try:
            sound = AudioSegment.from_file(str(input_path))
            sound = sound.set_frame_rate(16000).set_channels(1)
            sound.export(str(wav_path), format="wav")
            return True
        except Exception as e:
            voice_logger.warning(f"Convert to WAV failed: {e}")
            return False

    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🎙️ <b>Голосовой бот готов!</b>\n\n"
            "Отправь мне:\n"
            "• 🎤 Голосовое сообщение\n"
            "• 🎵 Аудиофайл\n"
            "• 📹 Видеосообщение (кружочек)\n\n"
            "Я транскрибирую и расставлю пунктуацию!",
            parse_mode="HTML"
        )

    async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

            mime_type = get_mime_type(msg)
            new_file = await context.bot.get_file(voice_obj.file_id)

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                input_path = temp_path / f"voice{ext}"
                wav_path = temp_path / "audio.wav"

                await new_file.download_to_drive(input_path)

                # 1. Gemini
                text = await recognize_gemini(input_path, mime_type)
                engine = "gemini" if text else None

                # 2. Google Fallback
                if not text:
                    if convert_to_wav(input_path, wav_path):
                        loop = asyncio.get_running_loop()
                        text = await loop.run_in_executor(None, recognize_google_sr, wav_path, "ru-RU")
                        if text:
                            engine = "google"
                        else:
                            text = await loop.run_in_executor(None, recognize_google_sr, wav_path, "en-US")
                            if text:
                                engine = "google_en"

                if text:
                    label = {"gemini": "✨ Gemini (HQ)", "google": "🔤 Google Speech", "google_en": "🔤 Google Speech (EN)"}.get(engine, "🔤")
                    await status.edit_text(f"🗣 <b>{text}</b>\n\n<i>{label}</i>", parse_mode="HTML")
                else:
                    await status.edit_text("❌ Не удалось распознать речь.\n\n<i>Попробуй отправить обычное голосовое</i>", parse_mode="HTML")

        except Exception as e:
            voice_logger.error(f"Error: {e}", exc_info=True)
            await status.edit_text(f"⚠️ Ошибка: {str(e)}")

    async def post_init(application: Application):
        await application.bot.delete_webhook(drop_pending_updates=True)
        voice_logger.info("Voice Bot polling started ✅")

    app = (
        ApplicationBuilder()
        .token(TOKEN_VOICE)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(
        filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE | filters.Document.AUDIO,
        handle_voice
    ))

    voice_logger.info("🎙️ Voice Bot запускается...")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        voice_logger.info("Voice Bot polling ✅")
        # Ждём пока задача не будет отменена
        await asyncio.Event().wait()


# ===================== MEDIA BOT =====================

async def run_media_bot():
    """Медиа бот на aiogram (polling)"""
    import tempfile
    import urllib.request
    import shutil
    import subprocess
    from aiogram import Bot, Dispatcher
    from aiogram.filters import CommandStart
    from aiogram.types import Message, FSInputFile, InputMediaPhoto
    from aiogram.enums import ParseMode
    from aiogram.client.default import DefaultBotProperties
    from aiogram.exceptions import TelegramRetryAfter
    from yt_dlp import YoutubeDL

    TOKEN_MEDIA = os.getenv("TOKEN_MEDIA")
    media_logger = logging.getLogger("media_bot")

    if not TOKEN_MEDIA:
        media_logger.error("[MediaBot] TOKEN_MEDIA не задан! Бот не запустится.")
        return

    MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

    bot = Bot(token=TOKEN_MEDIA, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    welcome_text = (
        "🌐 <b>Добро пожаловать в Media Bot!</b>\n\n"
        "Я скачиваю контент с популярных платформ!\n\n"
        "<b>Поддерживаемые сайты:</b>\n"
        "• 📸 Instagram (фото, видео, карусели)\n"
        "• 🎵 TikTok (видео, звук)\n"
        "• 📌 Pinterest (фото)\n\n"
        "<b>Как использовать:</b>\n"
        "Просто пришлите ссылку на пост!"
    )

    ALLOWED_DOMAINS = [
        'instagram.com', 'www.instagram.com',
        'pinterest.com', 'www.pinterest.com', 'pin.it',
        'tiktok.com', 'www.tiktok.com', 'vt.tiktok.com'
    ]

    @dp.message(CommandStart())
    async def cmd_start(message: Message):
        try:
            await message.answer(welcome_text)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            await message.answer(welcome_text)

    @dp.message(lambda m: m.text and ('http://' in m.text or 'https://' in m.text))
    async def handle_message(message: Message):
        url = message.text.strip() if message.text else None
        if not url:
            await message.reply("❌ Ссылка не найдена.")
            return

        if not any(domain in url.lower() for domain in ALLOWED_DOMAINS):
            await message.reply("❌ Ссылка должна быть с Instagram, TikTok или Pinterest")
            return

        status_msg = await message.reply("⏳ Скачиваю...")

        try:
            with tempfile.TemporaryDirectory() as tmpdirname:
                media_group = []

                if 'pin.it' in url or 'pinterest' in url.lower():
                    # Pinterest
                    try:
                        ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
                        with YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(url, download=False)
                        images = info.get('images', [])
                        if not images:
                            await status_msg.edit_text("❌ Не удалось найти фото в этом пине.")
                            return
                        for i, img in enumerate(images[:10]):
                            img_url = img.get('url') or img.get('src') or img.get('original')
                            if not img_url:
                                continue
                            filename = os.path.join(tmpdirname, f"pin_{i}.jpg")
                            urllib.request.urlretrieve(img_url, filename)
                            media_group.append(InputMediaPhoto(media=FSInputFile(filename)))
                        if not media_group:
                            await status_msg.edit_text("❌ Не удалось загрузить фото с Pinterest.")
                            return
                    except Exception as e:
                        await status_msg.edit_text(f"❌ Ошибка Pinterest: {str(e)}")
                        return
                else:
                    # TikTok / Instagram
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'outtmpl': os.path.join(tmpdirname, '%(id)s.%(ext)s'),
                        'format': 'bestvideo+bestaudio/best',
                        'merge_output_format': 'mp4',
                    }
                    with YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])

                    videos_found = [
                        os.path.join(tmpdirname, f)
                        for f in os.listdir(tmpdirname)
                        if f.lower().endswith(('.mp4', '.webm', '.mov'))
                    ]

                    if not videos_found:
                        await status_msg.edit_text("❌ Не удалось загрузить видео. Попробуйте другую ссылку.")
                        return

                    for file_path in videos_found:
                        size = os.path.getsize(file_path)
                        if size <= MAX_VIDEO_SIZE_BYTES:
                            await message.answer_video(video=FSInputFile(file_path), supports_streaming=True)
                        else:
                            ffmpeg_path = shutil.which('ffmpeg')
                            sent = False
                            if ffmpeg_path:
                                for crf in (23, 26, 28):
                                    transcoded = os.path.join(tmpdirname, f"transcoded_{crf}.mp4")
                                    try:
                                        subprocess.run([
                                            ffmpeg_path, '-y', '-i', file_path,
                                            '-c:v', 'libx264', '-crf', str(crf), '-preset', 'fast',
                                            '-c:a', 'aac', '-b:a', '96k', transcoded
                                        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                        if os.path.exists(transcoded) and os.path.getsize(transcoded) <= MAX_VIDEO_SIZE_BYTES:
                                            await message.answer_video(video=FSInputFile(transcoded), supports_streaming=True)
                                            sent = True
                                            break
                                    except Exception:
                                        continue
                            if not sent:
                                await message.answer_document(document=FSInputFile(file_path))
                        await status_msg.delete()
                        return

                # Pinterest фото
                if media_group:
                    if len(media_group) == 1:
                        await message.answer_photo(photo=media_group[0].media)
                    else:
                        await message.answer_media_group(media=media_group)
                    await status_msg.delete()

        except Exception as e:
            error_text = f"❌ Ошибка: {str(e)}\nПопробуйте другую ссылку."
            media_logger.error(f"Error: {e}", exc_info=True)
            try:
                await status_msg.edit_text(error_text)
            except Exception:
                await message.reply(error_text)

    # Удаляем старый webhook перед polling
    await bot.delete_webhook(drop_pending_updates=True)
    media_logger.info("🌐 Media Bot запускается...")
    await dp.start_polling(bot)


# ===================== LAUNCHER =====================

async def main():
    logger.info("=" * 50)
    logger.info("  Запуск ботов на Railway (polling режим)")
    logger.info("=" * 50)

    tasks = []

    voice_token = os.getenv("TOKEN_VOICE")
    media_token = os.getenv("TOKEN_MEDIA")

    if voice_token:
        logger.info("✅ TOKEN_VOICE найден — запускаю Voice Bot")
        tasks.append(asyncio.create_task(run_voice_bot()))
    else:
        logger.warning("⚠️  TOKEN_VOICE не задан — Voice Bot пропущен")

    if media_token:
        logger.info("✅ TOKEN_MEDIA найден — запускаю Media Bot")
        tasks.append(asyncio.create_task(run_media_bot()))
    else:
        logger.warning("⚠️  TOKEN_MEDIA не задан — Media Bot пропущен")

    if not tasks:
        logger.error("❌ Ни один токен не задан! Задай переменные среды TOKEN_VOICE и TOKEN_MEDIA.")
        return

    # Запускаем оба бота параллельно и ждём
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановлено вручную.")
