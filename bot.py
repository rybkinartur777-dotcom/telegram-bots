import asyncio
import os
import tempfile
import urllib.request
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile, InputMediaPhoto
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from yt_dlp import YoutubeDL
import shutil
import subprocess
import speech_recognition as sr
from pydub import AudioSegment

# Ограничение размера видео перед отправкой как "video" (в байтах). Если файл больше — будем транскодить или отправлять как документ.
MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024  # ~50 MB

TOKEN = "8509159747:AAEj-w7cc5lh35hkHB1rTDNW-Gb139NVcqM"

# Таблица транслитерации русских букв в латиницу
TRANSLIT_DICT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
    'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '"', 'ы': 'y', 'ь': "'", 'э': 'e', 'ю': 'yu',
    'я': 'ya',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh',
    'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O',
    'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'H', 'Ц': 'Ts',
    'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch', 'Ъ': '"', 'Ы': 'Y', 'Ь': "'", 'Э': 'E', 'Ю': 'Yu',
    'Я': 'Ya'
}

def transliterate(text):
    """Преобразует кириллицу в латиницу"""
    result = []
    for char in text:
        if char in TRANSLIT_DICT:
            result.append(TRANSLIT_DICT[char])
        else:
            result.append(char)
    return ''.join(result)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

welcome_text = (
    "Добро пожаловать!\n\n"
    "<b>🎙️ Голосовые сообщения:</b> Пришлите голосовое сообщение или аудиофайл, и я транскрибирую его и выведу транслит\n\n"
    "<b>🌐 Медиа из интернета:</b> Вы можете скинуть мне ссылку на пост в <b>Instagram</b>, <b>Pinterest</b> или <b>TikTok</b>, "
    "откуда нужно выгрузить фото, видео и текст — через пару секунд эта фотка или видос будут у вас!\n\n"
    "На данный момент я поддерживаю фото, видео, карусели из этих платформ."
)

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(welcome_text)

@dp.message()
async def handle_voice(message: Message):
    """Обработчик для голосовых сообщений"""
    if message.voice:
        try:
            status_msg = await message.reply("🔄 Обработка голосового сообщения...")
            
            with tempfile.TemporaryDirectory() as tmpdirname:
                # Скачиваем голосовой файл
                voice_file_path = os.path.join(tmpdirname, "voice.ogg")
                await bot.download(message.voice, destination=voice_file_path)
                
                # Конвертируем OGG в WAV для обработки
                audio = AudioSegment.from_ogg(voice_file_path)
                wav_path = os.path.join(tmpdirname, "voice.wav")
                audio.export(wav_path, format="wav")
                
                # Распознаём речь с Google Speech Recognition
                recognizer = sr.Recognizer()
                with sr.AudioFile(wav_path) as source:
                    audio_data = recognizer.record(source)
                
                try:
                    # Используем Google Speech Recognition API (бесплатный)
                    text = recognizer.recognize_google(audio_data, language='ru-RU')
                    
                    # Переводим в транслит
                    transliterated = transliterate(text)
                    
                    # Отправляем результат
                    result_text = (
                        f"<b>🎤 Голосовое сообщение распознано:</b>\n\n"
                        f"<b>Оригинал:</b>\n{text}\n\n"
                        f"<b>Транслит:</b>\n{transliterated}"
                    )
                    
                    await status_msg.edit_text(result_text)
                    
                except sr.UnknownValueError:
                    await status_msg.edit_text("❌ Не удалось распознать речь. Пожалуйста, проговорите яснее.")
                except sr.RequestError as e:
                    await status_msg.edit_text(f"❌ Ошибка сервиса распознавания: {str(e)}")
                    
        except Exception as e:
            await message.reply(f"❌ Ошибка при обработке: {str(e)}")
        return

    # Обработка аудиофайлов
    if message.audio:
        try:
            status_msg = await message.reply("🔄 Обработка аудиофайла...")
            
            with tempfile.TemporaryDirectory() as tmpdirname:
                # Скачиваем аудиофайл
                audio_file_path = os.path.join(tmpdirname, "audio.mp3")
                await bot.download(message.audio, destination=audio_file_path)
                
                # Конвертируем в WAV для обработки (если нужно)
                try:
                    audio = AudioSegment.from_mp3(audio_file_path)
                except:
                    # Пробуем другие форматы
                    audio = AudioSegment.from_file(audio_file_path)
                
                wav_path = os.path.join(tmpdirname, "audio.wav")
                audio.export(wav_path, format="wav")
                
                # Распознаём речь
                recognizer = sr.Recognizer()
                with sr.AudioFile(wav_path) as source:
                    audio_data = recognizer.record(source)
                
                try:
                    text = recognizer.recognize_google(audio_data, language='ru-RU')
                    transliterated = transliterate(text)
                    
                    result_text = (
                        f"<b>🎵 Аудиофайл распознан:</b>\n\n"
                        f"<b>Оригинал:</b>\n{text}\n\n"
                        f"<b>Транслит:</b>\n{transliterated}"
                    )
                    
                    await status_msg.edit_text(result_text)
                    
                except sr.UnknownValueError:
                    await status_msg.edit_text("❌ Не удалось распознать речь в аудиофайле.")
                except sr.RequestError as e:
                    await status_msg.edit_text(f"❌ Ошибка сервиса: {str(e)}")
                    
        except Exception as e:
            await message.reply(f"❌ Ошибка при обработке аудиофайла: {str(e)}")
        return

@dp.message()
async def handle_message(message: Message):

    allowed_domains = [
        'instagram.com', 'www.instagram.com',
        'pinterest.com', 'www.pinterest.com', 'pin.it',
        'tiktok.com', 'www.tiktok.com'
    ]
    if not message.text or not ('http://' in message.text or 'https://' in message.text):
        return  # Просто игнорируем сообщения без ссылок

    url = message.text.strip()
    # Проверяем, есть ли разрешённый домен в ссылке
    if not any(domain in url.lower() for domain in allowed_domains):
        return  # Не реагируем на другие ссылки или текст

    status_msg = await message.reply("Обработка ссылки, подождите...")

    try:
        with tempfile.TemporaryDirectory() as tmpdirname:
            media_group = []
            caption = ""

            # Извлекаем только информацию (без скачивания видео)
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,  # не скачиваем видео
                'format': 'bestvideo+bestaudio/best',  # максимальное качество
                'merge_output_format': 'mp4',
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            # Не используем подпись (caption) вообще
            caption = ""

            # Специальный блок для Pinterest — прямое скачивание фото
            if 'pin.it' in url or 'pinterest' in url.lower():
                images = info.get('images', [])
                if not images:
                    await status_msg.edit_text("Не удалось найти фото в этом пине (возможно, приватный пост).")
                    return
                for i, img in enumerate(images[:10]):
                    img_url = img.get('url') or img.get('src') or img.get('original')
                    if not img_url:
                        continue
                    filename = os.path.join(tmpdirname, f"pin_{i}.jpg")
                    urllib.request.urlretrieve(img_url, filename)
                    media_group.append(InputMediaPhoto(media=FSInputFile(filename)))
            else:
                # Для TikTok/Instagram — скачиваем нормально
                ydl_opts['skip_download'] = False
                ydl_opts['outtmpl'] = os.path.join(tmpdirname, '%(id)s.%(ext)s')
                ydl_opts['format'] = 'bestvideo+bestaudio/best'  # максимальное качество
                ydl_opts['merge_output_format'] = 'mp4'
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                for file in os.listdir(tmpdirname):
                    file_path = os.path.join(tmpdirname, file)
                    if file.lower().endswith(('.mp4', '.webm', '.mov')):
                        # Проверяем размер и при необходимости транскодируем через ffmpeg
                        size = os.path.getsize(file_path)
                        sent = False

                        if size <= MAX_VIDEO_SIZE_BYTES:
                            await message.answer_video(video=FSInputFile(file_path), supports_streaming=True)
                            sent = True
                        else:
                            # пытаемся транскодировать при наличии ffmpeg
                            ffmpeg_path = shutil.which('ffmpeg')
                            if ffmpeg_path:
                                # Попробуем несколько значений CRF для баланса качества/размера
                                for crf in (18, 20, 23, 28):
                                    transcoded = os.path.join(tmpdirname, f"transcoded_{crf}.mp4")
                                    try:
                                        subprocess.run([
                                            ffmpeg_path, '-y', '-i', file_path,
                                            '-c:v', 'libx264', '-crf', str(crf), '-preset', 'medium',
                                            '-c:a', 'aac', '-b:a', '128k', transcoded
                                        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                    except Exception:
                                        continue

                                    if os.path.exists(transcoded):
                                        new_size = os.path.getsize(transcoded)
                                        if new_size <= MAX_VIDEO_SIZE_BYTES:
                                            await message.answer_video(video=FSInputFile(transcoded), supports_streaming=True)
                                            sent = True
                                            break
                                # если не удалось уменьшить до лимита, отправляем крупный файл как документ
                            if not sent:
                                await message.answer_document(document=FSInputFile(file_path))
                                sent = True

                        if sent:
                            await status_msg.delete()
                            return
                    else:
                        media_group.append(InputMediaPhoto(media=FSInputFile(file_path)))

            if not media_group:
                await status_msg.edit_text("Не удалось найти медиа по этой ссылке.")
                return



            if len(media_group) == 1:
                file_path = media_group[0].media
                await message.answer_photo(photo=file_path)
                await message.answer_document(document=file_path)
            else:
                await message.answer_media_group(media=media_group)

            await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"Ошибка обработки: {e}\nПопробуйте другую ссылку или обновите yt-dlp.")

async def main():
    print("Бот запущен и готов!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())