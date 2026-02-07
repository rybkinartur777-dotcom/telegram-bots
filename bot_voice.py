async def process_voice(message, voice_obj):
    status = await message.reply("🎤 Слушаю голос...")
    temp_dir = tempfile.gettempdir()
    ts = int(time.time() * 1000)
    ogg_file = os.path.join(temp_dir, f"voice{ts}.ogg")
    wav_file = os.path.join(temp_dir, f"voice{ts}.wav")
    # Скачиваем голосовое
    ok = await download_with_retries(voice_obj, ogg_file, attempts=3, delay=0.12)
    if not ok:
        await status.edit_text("❌ Не удалось загрузить голосовое сообщение.")
        return
    # Конвертируем в WAV
    if not convert_to_wav(ogg_file, wav_file):
        await status.edit_text("❌ Conversion failed (ffmpeg)")
        return
    await asyncio.sleep(1.0)
    if not os.path.exists(wav_file):
        await status.edit_text(f"❌ No output WAV file after conversion")
        return
    wav_size = os.path.getsize(wav_file)
    print(f"[DEBUG] WAV file path: {wav_file}, size: {wav_size} bytes")
    # Распознаём
    if WHISPER_AVAILABLE:
        rec, det_lang = transcribe_with_whisper(wav_file)
        if rec:
            recognized_text = rec
            detected_lang = det_lang or 'whisper'
        else:
            recognized_text, detected_lang, _, _ = recognize_file_multilang(wav_file, languages=("ru-RU", "en-US"))
    else:
        recognized_text, detected_lang, _, _ = recognize_file_multilang(wav_file, languages=("ru-RU", "en-US"))
    if not recognized_text:
        await status.edit_text("❌ Не удалось распознать речь")
        return
    text = restore_punctuation(recognized_text)
    await status.edit_text(text)

async def process_audio(message, audio_obj):
    await message.reply("[DEBUG] process_audio: обработка аудиофайла")

async def process_video(message, video_obj):
    await message.reply("[DEBUG] process_video: обработка видео-заметки")
async def process_voice(message, voice_obj):
    status = await message.reply("🎤 Слушаю голос...")
    temp_dir = tempfile.gettempdir()
    ts = int(time.time() * 1000)
    ogg_file = os.path.join(temp_dir, f"voice{ts}.ogg")
    wav_file = os.path.join(temp_dir, f"voice{ts}.wav")
    # Скачиваем голосовое
    ok = await download_with_retries(voice_obj, ogg_file, attempts=3, delay=0.12)
    if not ok:
        await status.edit_text("❌ Не удалось загрузить голосовое сообщение.")
        return
    # Конвертируем в WAV
    if not convert_to_wav(ogg_file, wav_file):
        await status.edit_text("❌ Conversion failed (ffmpeg)")
        return
    await asyncio.sleep(1.0)
    if not os.path.exists(wav_file):
        await status.edit_text(f"❌ No output WAV file after conversion")
        return
    # Распознаём
    if WHISPER_AVAILABLE:
        rec, det_lang = transcribe_with_whisper(wav_file)
        if rec:
            recognized_text = rec
            detected_lang = det_lang or 'whisper'
        else:
            recognized_text, detected_lang, _, _ = recognize_file_multilang(wav_file, languages=("ru-RU", "en-US"))
    else:
        recognized_text, detected_lang, _, _ = recognize_file_multilang(wav_file, languages=("ru-RU", "en-US"))
    if not recognized_text:
        await status.edit_text("❌ Не удалось распознать речь")
        return
    text = restore_punctuation(recognized_text)
    await status.edit_text(text)

async def process_audio(message, audio_obj):
    await message.reply("[DEBUG] process_audio: обработка аудиофайла")

async def process_video(message, video_obj):
    await message.reply("[DEBUG] process_video: обработка видео-заметки")
async def process_voice(message, voice_obj):
    status = await message.reply("🎤 Слушаю голос...")
    temp_dir = tempfile.gettempdir()
    ts = int(time.time() * 1000)
    ogg_file = os.path.join(temp_dir, f"voice{ts}.ogg")
    wav_file = os.path.join(temp_dir, f"voice{ts}.wav")
    # Скачиваем голосовое
    ok = await download_with_retries(voice_obj, ogg_file, attempts=3, delay=0.12)
    if not ok:
        await status.edit_text("❌ Не удалось загрузить голосовое сообщение.")
        return
    # Конвертируем в WAV
    if not convert_to_wav(ogg_file, wav_file):
        await status.edit_text("❌ Conversion failed (ffmpeg)")
        return
    await asyncio.sleep(1.0)
    if not os.path.exists(wav_file):
        await status.edit_text(f"❌ No output WAV file after conversion")
        return
    # Распознаём
    if WHISPER_AVAILABLE:
        rec, det_lang = transcribe_with_whisper(wav_file)
        if rec:
            recognized_text = rec
            detected_lang = det_lang or 'whisper'
        else:
            recognized_text, detected_lang, _, _ = recognize_file_multilang(wav_file, languages=("ru-RU", "en-US"))
    else:
        recognized_text, detected_lang, _, _ = recognize_file_multilang(wav_file, languages=("ru-RU", "en-US"))
    if not recognized_text:
        await status.edit_text("❌ Не удалось распознать речь")
        return
    text = restore_punctuation(recognized_text)
    await status.edit_text(text)

async def process_audio(message, audio_obj):
    await message.reply("[DEBUG] process_audio: обработка аудиофайла")

async def process_video(message, video_obj):
    await message.reply("[DEBUG] process_video: обработка видео-заметки")
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

# Загружаем переменные окружения из .env файла
load_dotenv()


# ===== FFMPEG SETUP =====
FFMPEG_PATH = None
local_ffmpeg = os.path.join(os.path.dirname(__file__), "ffmpeg", "ffmpeg.exe")
if os.path.exists(local_ffmpeg):
    FFMPEG_PATH = local_ffmpeg
    print(f"[FFmpeg] Using local: {FFMPEG_PATH}")
else:
    FFMPEG_PATH = shutil.which("ffmpeg")
    if FFMPEG_PATH:
        print(f"[FFmpeg] Using system: {FFMPEG_PATH}")
    else:
        print("[WARNING] FFmpeg not found!")

# ===== CONFIG =====
TOKEN_VOICE = os.getenv("TOKEN_VOICE", "YOUR_TOKEN_HERE")

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
    """Convert Cyrillic to Latin"""
    result = []
    for char in text:
        result.append(TRANSLIT_DICT.get(char, char))
    return ''.join(result)

def add_punctuation(text):
    """Add punctuation to text"""
    text = text.strip()
    if not text:
        return text
    
    # Capitalize first letter
    text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
    
    # Add period at the end if missing
    if not text.endswith(('.', '!', '?', ':', ';')):
        text += '.'
    
    return text

def convert_to_wav(input_file, output_file):
    """Convert any audio to WAV 16000Hz mono using ffmpeg"""
    if not FFMPEG_PATH:
        print("[ERROR] FFmpeg not found")
        return False
    try:
        # Используем sample rate 48000 Hz для совместимости с opus/ogg
        cmd = [FFMPEG_PATH, '-y', '-i', input_file, '-ar', '48000', '-ac', '1', '-f', 'wav', output_file]
        print(f"[FFmpeg CMD] {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        print(f"[FFmpeg STDOUT] {result.stdout.decode(errors='ignore')[:300]}")
        if result.stderr:
            print(f"[FFmpeg STDERR] {result.stderr.decode(errors='ignore')[:300]}")
        success = result.returncode == 0 and os.path.exists(output_file)
        if not success:
            print(f"[FFmpeg Error] Return code: {result.returncode}")
        return success
    except Exception as e:
        print(f"[ERROR] convert_to_wav: {str(e)}")
        return False


async def download_with_retries(file_obj, dest_path, attempts=3, delay=0.12):
    """Download Telegram file with retries. Returns True on success."""
    for i in range(attempts):
        try:
            await bot.download(file_obj, destination=dest_path)
        except Exception as e:
            print(f"[Download] attempt {i+1} failed: {e}")
            await asyncio.sleep(delay)
            continue

        # give OS a moment to flush
        await asyncio.sleep(0.06)
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
            return True
        else:
            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except:
                pass
            await asyncio.sleep(delay)
    return False


def try_import_punctuator():
    """Try to import DeepMultilingualPunctuation; return instance or None."""
    try:
        from deepmultilingualpunctuation import PunctuationModel
        model = PunctuationModel()
        print("[Punctuator] Using DeepMultilingualPunctuation")
        return model
    except Exception:
        print("[Punctuator] deepmultilingualpunctuation not available, using fallback")
        return None


PUNCTUATOR = try_import_punctuator()


def restore_punctuation(text: str) -> str:
    """Restore punctuation using model if available, else simple heuristic."""
    if not text:
        return text
    if PUNCTUATOR:
        try:
            return PUNCTUATOR.add_punctuation(text)
        except Exception:
            pass

    # Simple heuristic fallback: capitalize and add final period if missing
    t = text.strip()
    if len(t) > 1:
        t = t[0].upper() + t[1:]
    if not re.search(r"[.!?]$", t):
        t = t + '.'
    return t


# ===== WHISPER (local) =====
WHISPER_AVAILABLE = False
WHISPER_MODEL = None
WHISPER_MODEL_NAME = os.environ.get('WHISPER_MODEL', 'medium')
WHISPER_LANG = os.environ.get('WHISPER_LANG', 'ru')
try:
    import whisper
    try:
        print(f"[Whisper] Loading model: {WHISPER_MODEL_NAME}")
        WHISPER_MODEL = whisper.load_model(WHISPER_MODEL_NAME)
        WHISPER_AVAILABLE = True
        print(f"[Whisper] Model '{WHISPER_MODEL_NAME}' loaded")
    except Exception as e:
        print(f"[Whisper] Failed to load model '{WHISPER_MODEL_NAME}': {e}")
except Exception:
    print("[Whisper] package not available")


def transcribe_with_whisper(wav_path):
    """Transcribe using local Whisper model. Returns (text, language) or (None, None)."""
    if not WHISPER_AVAILABLE or WHISPER_MODEL is None:
        return None, None
    try:
        # Preprocess: normalize and trim silence to improve accuracy
        tmp = None
        try:
            tmp = wav_path + ".pre.wav"
            preprocess_audio(wav_path, tmp)
            trans_input = tmp
        except Exception:
            trans_input = wav_path

        # Whisper options: force language if provided, use beam search for better accuracy
        opts = {
            'language': WHISPER_LANG if WHISPER_LANG else None,
            'temperature': 0.0,
            'beam_size': 5,
        }
        # remove None values
        clean_opts = {k: v for k, v in opts.items() if v is not None}
        res = WHISPER_MODEL.transcribe(trans_input, **clean_opts)
        text = res.get('text', '') if isinstance(res, dict) else str(res)
        lang = res.get('language') if isinstance(res, dict) else None
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except:
                pass
        if text is None:
            return None, None
        return text.strip(), lang
    except Exception as e:
        print(f"[Whisper] transcribe error: {e}")
        return None, None


def preprocess_audio(in_wav, out_wav, target_sr=16000):
    """Normalize, high-pass filter and trim silence. Exports 16k mono WAV."""
    seg = AudioSegment.from_file(in_wav)
    # apply high pass filter to remove low rumble
    try:
        seg = seg.high_pass_filter(100.0)
    except Exception:
        pass
    # normalize loudness
    seg = effects.normalize(seg)

    # detect non-silent ranges
    nonsil = silence.detect_nonsilent(seg, min_silence_len=300, silence_thresh=seg.dBFS - 16)
    if nonsil:
        start = max(0, nonsil[0][0] - 150)
        end = min(len(seg), nonsil[-1][1] + 150)
        seg = seg[start:end]

    seg = seg.set_frame_rate(target_sr).set_channels(1).set_sample_width(2)
    seg.export(out_wav, format='wav')


def recognize_file_multilang(wav_path, languages=("ru-RU", "en-US"), timeout=12):
    """Recognize audio in multiple languages in parallel.
    Returns tuple: (best_text, best_lang, results_dict, scores_dict)
    results_dict: {lang: text_or_None}
    scores_dict: {lang: score_int}
    """
    recognizer = sr.Recognizer()

    def recognize_lang(lang):
        try:
            with sr.AudioFile(wav_path) as source:
                audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language=lang)
            return lang, text
        except Exception:
            return lang, None

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(languages)) as ex:
        futures = {ex.submit(recognize_lang, lang): lang for lang in languages}
        try:
            for fut in concurrent.futures.as_completed(futures, timeout=timeout):
                lang = futures[fut]
                try:
                    l, text = fut.result()
                    results[l] = text
                except Exception:
                    results[lang] = None
        except concurrent.futures.TimeoutError:
            pass

    # scoring heuristic
    def score(lang, txt):
        if not txt:
            return -9999
        cyr = len(re.findall(r'[\u0400-\u04FF]', txt))
        lat = len(re.findall(r'[A-Za-z]', txt))
        if lang.startswith('ru'):
            return cyr - lat
        if lang.startswith('en'):
            return lat - cyr
        return lat + cyr

    scores = {}
    best_lang = None
    best_text = None
    best_score = -9999
    for lang, txt in results.items():
        s = score(lang, txt)
        scores[lang] = s
        if s > best_score:
            best_score = s
            best_lang = lang
            best_text = txt

    # fallback sequential tries
    if not best_text:
        for lang in languages:
            try:
                with sr.AudioFile(wav_path) as source:
                    audio = recognizer.record(source)
                txt = recognizer.recognize_google(audio, language=lang)
                if txt:
                    # set results and scores for fallback
                    results[lang] = txt
                    scores[lang] = score(lang, txt)
                    return txt, lang, results, scores
            except Exception:
                continue
        return "", None, results, scores

    return best_text, best_lang, results, scores

# ===== BOT =====
bot = Bot(token=TOKEN_VOICE, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Voice Bot ready!\nSend me voice messages, audio files, or video notes.")

@dp.message()
async def handle_message(message: Message):
    """Handle voice messages, audio files, and video notes"""
    
    # Универсальная обработка voice/audio/video_note
    try:
        voice_obj = message.voice or (getattr(message, 'reply_to_message', None) and getattr(message.reply_to_message, 'voice', None))
        audio_obj = message.audio or (getattr(message, 'reply_to_message', None) and getattr(message.reply_to_message, 'audio', None))
        video_obj = message.video_note or (getattr(message, 'reply_to_message', None) and getattr(message.reply_to_message, 'video_note', None))

        if voice_obj:
            await process_voice(message, voice_obj)
            return
        if audio_obj:
            await process_audio(message, audio_obj)
            return
        if video_obj:
            await process_video(message, video_obj)
            return
    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")
    
    # VIDEO NOTES
    if message.video_note:
        status = await message.reply("🎬 Слушаю видео...")
        temp_dir = tempfile.gettempdir()
        ts = int(time.time() * 1000)
        mp4_file = os.path.join(temp_dir, f"vn{ts}.mp4")
        wav_file = os.path.join(temp_dir, f"vn{ts}.wav")
        # Download
        print(f"[Download] Saving to: {mp4_file}")
        ok = await download_with_retries(message.video_note, mp4_file, attempts=3, delay=0.12)
        if not ok:
            await status.edit_text("❌ Не удалось загрузить видеофайл.")
            return
        # Универсальная обработка video_note (оригинал, reply, пересланное)
        video_obj = None
        if message.video_note:
            video_obj = message.video_note
        elif getattr(message, 'reply_to_message', None) and getattr(message.reply_to_message, 'video_note', None):
            video_obj = message.reply_to_message.video_note
        elif getattr(message, 'forward_from', None) and getattr(message, 'video_note', None):
            video_obj = message.video_note
        if video_obj:
                    status = await message.reply("🎬 Слушаю видео...")
                    temp_dir = tempfile.gettempdir()
                    ts = int(time.time() * 1000)
                    mp4_file = os.path.join(temp_dir, f"vn{ts}.mp4")
                    wav_file = os.path.join(temp_dir, f"vn{ts}.wav")
                    # Download
                    print(f"[Download] Saving to: {mp4_file}")
                    ok = await download_with_retries(video_obj, mp4_file, attempts=3, delay=0.12)
                    if not ok:
                        await status.edit_text("❌ Не удалось загрузить видеофайл.")
                        return
                    # Convert
                    print(f"[Convert] MP4 -> WAV: {mp4_file} -> {wav_file}")
                    if not convert_to_wav(mp4_file, wav_file):
                        await status.edit_text("❌ Conversion failed (ffmpeg)")
                        return
                    await asyncio.sleep(1.0)
                    if not os.path.exists(wav_file):
                        await status.edit_text(f"❌ No output WAV file after conversion")
                        return
                    print(f"[Recognize] Loading WAV: {wav_file}")
                    if WHISPER_AVAILABLE:
                        rec, det_lang = transcribe_with_whisper(wav_file)
                        if rec:
                            recognized_text = rec
                            detected_lang = det_lang or 'whisper'
                            results = {detected_lang: recognized_text}
                            scores = {detected_lang: 9999}
                        else:
                            recognized_text, detected_lang, results, scores = recognize_file_multilang(wav_file, languages=("ru-RU", "en-US"))
                    else:
                        recognized_text, detected_lang, results, scores = recognize_file_multilang(wav_file, languages=("ru-RU", "en-US"))
                    if not recognized_text:
                        await status.edit_text("❌ Не удалось распознать речь")
                        return
                    text = restore_punctuation(recognized_text)
                    await status.edit_text(text)

if __name__ == "__main__":
    async def main():
        await dp.start_polling(bot)

    asyncio.run(main())
