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
import whisper
import re

MAX_VIDEO_SIZE_BYTES = 50 * 1024 * 1024

TOKEN = "8509159747:AAEj-w7cc5lh35hkHB1rTDNW-Gb139NVcqM"

print("🔄 Загрузка модели Whisper...")
whisper_model = whisper.load_model("base")
print("✅ Модель Whisper загружена!")

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
    result = []
    for char in text:
        result.append(TRANSLIT_DICT.get(char, char))
    return ''.join(result)

def add_smart_punctuation(text):
    """Агрессивная расстановка запятых"""
    
    # Делаем первую букву заглавной
    if text:
        text = text[0].upper() + text[1:]
    
    # Вопросительные фразы - после них запятая
    questions = [
        'как дела', 'как ты', 'как у тебя', 'как у вас', 'что делаешь', 
        'что делаете', 'что случилось', 'что произошло', 'как жизнь',
        'как настроение', 'как сам', 'как сама'
    ]
    for q in questions:
        text = re.sub(rf'({q})', r'\1,', text, flags=re.IGNORECASE)
    
    # Слова-маркеры, перед которыми запятая
    before_comma = [
        'потому что', 'так как', 'поэтому', 'хотя', 'если', 'когда', 
        'пока', 'чтобы', 'что', 'который', 'где', 'куда', 'почему', 'зачем',
        'но', 'а', 'или', 'либо', 'то есть', 'как'
    ]
    for word in sorted(before_comma, key=len, reverse=True):
        pattern = rf'(?<!^)(?<![.,!?])(?<!\s,) ({word})'
        text = re.sub(pattern, f', {word}', text, flags=re.IGNORECASE)
    
    # Вводные слова - с двух сторон запятые 
    introductory = [
        'конечно', 'наверное', 'возможно', 'кстати', 'например',
        'видимо', 'очевидно', 'значит', 'итак', 'впрочем', 'однако'
    ]
    for word in introductory:
        # В начале
        text = re.sub(rf'^{word}\s', f'{word.capitalize()}, ', text, flags=re.IGNORECASE)
        # В середине
        text = re.sub(rf'(?<![.,!?])\s({word})\s', r', \1, ', text, flags=re.IGNORECASE)
    
    # После приветствий - запятая
    greetings = ['привет', 'здравствуй', 'здравствуйте', 'добрый день', 'добрый вечер', 'доброе утро', 'здорово']
    for gr in greetings:
        text = re.sub(rf'^({gr})', r'\1,', text, flags=re.IGNORECASE)
    
    # После да/нет/ну/ладно в начале
    text = re.sub(r'^(да|нет|ну|ладно|хорошо|отлично)\s', r'\1, ', text, flags=re.IGNORECASE)
    
    # Каждые 7-8 слов ставим запятую (имитация естественной речи)
    words = text.split()
    if len(words) > 8:
        result = []
        for i, word in enumerate(words):
            result.append(word)
            # Ставим запятую каждые 7 слов, если там еще нет знака препинания
            if (i + 1) % 7 == 0 and i < len(words) - 1:
                if not word.endswith((',', '.', '!', '?')):
                    result[-1] = word + ','
        text = ' '.join(result)
    
    # Убираем двойные/тройные запятые
    text = re.sub(r',(\s*,)+', ',', text)
    
    # Убираем запятую перед точкой
    text = re.sub(r',\s*\.', '.', text)
    
    # Точка в конце
    if text and text[-1] not in '.!?':
        text += '.'
    
    # Заглавная после точки
    text = re.sub(r'([.!?]\s+)([а-яё])', lambda m: m.group(1) + m.group(2).upper(), text)
    
    # Пробелы после запятых
    text = re.sub(r',([^\s])', r', \1', text)
    
    return text


bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

welcome_text = (
    "Добро пожаловать!\n\n"
    "<b>🎙️ Голосовые сообщения:</b> Пришлите голосовое сообщение - я добавлю пунктуацию!\n\n"
    "<b>🌐 Медиа:</b> Instagram, Pinterest, TikTok\n\n"
    "✨ <b>Умная расстановка запятых!</b>"
)

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(welcome_text)

@dp.message()
async def handle_voice(message: Message):
    if message.voice:
        try:
            status_msg = await message.reply("🔄 Обработка...")
            
            with tempfile.TemporaryDirectory() as tmpdirname:
                voice_file_path = os.path.join(tmpdirname, "voice.ogg")
                await bot.download(message.voice, destination=voice_file_path)
                
                audio_path = os.path.join(tmpdirname, "voice.mp3")
                ffmpeg_path = shutil.which('ffmpeg')
                if ffmpeg_path:
                    try:
                        subprocess.run([
                            ffmpeg_path, '-y', '-i', voice_file_path,
                            '-ar', '16000', '-ac', '1', audio_path
                        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except:
                        audio_path = voice_file_path
                else:
                    audio_path = voice_file_path
                
                try:
                    result = whisper_model.transcribe(audio_path, language='ru', fp16=False)
                    text_raw = result['text'].strip().lower()
                    text_punct = add_smart_punctuation(text_raw)
                    transliterated = transliterate(text_punct)
                    
                    result_text = (
                        f"<b>🎤 Распознано:</b>\n\n"
                        f"<b>Оригинал:</b>\n{text_punct}\n\n"
                        f"<b>Транслит:</b>\n{transliterated}"
                    )
                    
                    await status_msg.edit_text(result_text)
                except Exception as e:
                    await status_msg.edit_text(f"❌ Ошибка: {str(e)}")
        except Exception as e:
            await message.reply(f"❌ Ошибка: {str(e)}")
        return

    if message.audio:
        try:
            status_msg = await message.reply("🔄 Обработка...")
            
            with tempfile.TemporaryDirectory() as tmpdirname:
                audio_file_path = os.path.join(tmpdirname, "audio")
                await bot.download(message.audio, destination=audio_file_path)
                
                try:
                    result = whisper_model.transcribe(audio_file_path, language='ru', fp16=False)
                    text_raw = result['text'].strip().lower()
                    text_punct = add_smart_punctuation(text_raw)
                    transliterated = transliterate(text_punct)
                    
                    result_text = (
                        f"<b>🎵 Распознано:</b>\n\n"
                        f"<b>Оригинал:</b>\n{text_punct}\n\n"
                        f"<b>Транслит:</b>\n{transliterated}"
                    )
                    
                    await status_msg.edit_text(result_text)
                except Exception as e:
                    await status_msg.edit_text(f"❌ Ошибка: {str(e)}")
        except Exception as e:
            await message.reply(f"❌ Ошибка: {str(e)}")
        return

@dp.message()
async def handle_message(message: Message):
    allowed_domains = ['instagram.com', 'www.instagram.com', 'pinterest.com', 'www.pinterest.com', 
                       'pin.it', 'tiktok.com', 'www.tiktok.com']
    if not message.text or not ('http://' in message.text or 'https://' in message.text):
        return
    
    url = message.text.strip()
    if not any(domain in url.lower() for domain in allowed_domains):
        return
    
    status_msg = await message.reply("Обработка...")
    
    try:
        with tempfile.TemporaryDirectory() as tmpdirname:
            media_group = []
            
            ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 
                       'format': 'bestvideo+bestaudio/best', 'merge_output_format': 'mp4'}
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            
            if 'pin.it' in url or 'pinterest' in url.lower():
                images = info.get('images', [])
                if not images:
                    await status_msg.edit_text("Не удалось найти фото.")
                    return
                for i, img in enumerate(images[:10]):
                    img_url = img.get('url') or img.get('src') or img.get('original')
                    if img_url:
                        filename = os.path.join(tmpdirname, f"pin_{i}.jpg")
                        urllib.request.urlretrieve(img_url, filename)
                        media_group.append(InputMediaPhoto(media=FSInputFile(filename)))
            else:
                ydl_opts['skip_download'] = False
                ydl_opts['outtmpl'] = os.path.join(tmpdirname, '%(id)s.%(ext)s')
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
                await status_msg.edit_text("Не удалось найти медиа.")
                return
            
            if len(media_group) == 1:
                file_path = media_group[0].media
                await message.answer_photo(photo=file_path)
                await message.answer_document(document=file_path)
            else:
                await message.answer_media_group(media=media_group)
            
            await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"Ошибка: {e}")

async def main():
    print("Бот запущен и готов!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
