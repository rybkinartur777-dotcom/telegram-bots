
import asyncio
import os
import tempfile
import urllib.request
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile, InputMediaPhoto
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from yt_dlp import YoutubeDL
import shutil
import subprocess

# Загружаем переменные окружения
load_dotenv()

# ===== КОНФИГУРАЦИЯ =====
TOKEN_MEDIA = os.getenv("TOKEN_MEDIA", "YOUR_TOKEN_HERE")

# Ограничение размера видео
MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024  # ~50 MB

# ===== ИНИЦИАЛИЗАЦИЯ БОТА =====
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

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.answer(welcome_text)

@dp.message(lambda message: message.text and ('http://' in message.text or 'https://' in message.text))
async def handle_message(message: Message):
    """Обработчик для ссылок на медиа"""
    
    allowed_domains = [
        'instagram.com', 'www.instagram.com',
        'pinterest.com', 'www.pinterest.com', 'pin.it',
        'tiktok.com', 'www.tiktok.com', 'vt.tiktok.com'
    ]
    
    # Универсальный поиск ссылки
    url = None
    if message.text and ('http://' in message.text or 'https://' in message.text):
        url = message.text.strip()
    
    if not url:
        await message.reply("❌ Не найдена ссылка для обработки.")
        return
    
    # Проверяем, есть ли разрешённый домен в ссылке
    if not any(domain in url.lower() for domain in allowed_domains):
        await message.reply("❌ Ссылка должна быть с Instagram, TikTok или Pinterest")
        return

    status_msg = await message.reply("⏳ Скачиваю...")

    try:
        with tempfile.TemporaryDirectory() as tmpdirname:
            media_group = []

            # Специальный блок для Pinterest — работаем с фото
            if 'pin.it' in url or 'pinterest' in url.lower():
                try:
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'skip_download': True,
                    }
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
                # Для TikTok/Instagram — скачиваем видео/фото
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'outtmpl': os.path.join(tmpdirname, '%(id)s.%(ext)s'),
                    'format': 'bestvideo+bestaudio/best',
                    'merge_output_format': 'mp4',
                }
                
                print(f"[DEBUG] Downloading from: {url}")
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                # Ищем загруженные файлы
                videos_found = []
                for file in os.listdir(tmpdirname):
                    file_path = os.path.join(tmpdirname, file)
                    if file.lower().endswith(('.mp4', '.webm', '.mov')):
                        videos_found.append(file_path)
                        print(f"[DEBUG] Found video: {file}")
                
                if not videos_found:
                    await status_msg.edit_text("❌ Не удалось загрузить видео. Попробуйте другую ссылку.")
                    return
                
                # Обрабатываем каждое видео
                for file_path in videos_found:
                    size = os.path.getsize(file_path)
                    print(f"[DEBUG] Video size: {size / 1024 / 1024:.2f} MB")
                    
                    if size <= MAX_VIDEO_SIZE_BYTES:
                        # Отправляем как видео
                        await message.answer_video(video=FSInputFile(file_path), supports_streaming=True)
                    else:
                        # Пробуем транскодировать если ffmpeg есть
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
                                    
                                    if os.path.exists(transcoded):
                                        new_size = os.path.getsize(transcoded)
                                        if new_size <= MAX_VIDEO_SIZE_BYTES:
                                            await message.answer_video(video=FSInputFile(transcoded), supports_streaming=True)
                                            sent = True
                                            break
                                except Exception:
                                    continue
                        
                        # Если не удалось сжать, отправляем как документ
                        if not sent:
                            await message.answer_document(document=FSInputFile(file_path))
                    
                    await status_msg.delete()
                    return

            # Отправляем фото (для Pinterest)
            if media_group:
                if len(media_group) == 1:
                    photo_file = media_group[0].media
                    await message.answer_photo(photo=photo_file)
                else:
                    await message.answer_media_group(media=media_group)
                await status_msg.delete()

    except Exception as e:
        error_text = f"❌ Ошибка: {str(e)}\nПопробуйте другую ссылку."
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        try:
            await status_msg.edit_text(error_text)
        except:
            await message.reply(error_text)

async def main():
    print("🌐 Media Bot запущен (локальный режим - polling)")
    print("Бот готов к работе!")
    
    # Удаляем webhook если был установлен
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
