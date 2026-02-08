
import asyncio
import os
import logging
import random
import sys
from collections import deque
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler

# Новая библиотека Google GenAI
from google import genai
from google.genai import types

load_dotenv()
TOKEN_GROUP = os.getenv("TOKEN_GROUP")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - [Angelina] - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CLIENT SETUP ---
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Angelina initialized (Gemini Client created).")
    except Exception as e:
        logger.error(f"Failed to init details: {e}")

# --- MEMORY ---
CHAT_HISTORY = deque(maxlen=200)

# --- PERSONA ---
SYSTEM_PROMPT = """
Тебя зовут Ангелина. Ты девушка, 23 года.
Ты находишься в чате telegram с друзьями/коллегами.
Твоя задача: общаться как живой человек. Не веди себя как робот-ассистент.
- Ты можешь шутить, сарказмировать (по-доброму), отвечать на вопросы.
- Если спрашивают что-то умное/техническое — включай режим эксперта и отвечай подробно.
- Если спрашивают просто "как дела" — отвечай легко.
- Не используй фразы "Как искусственный интеллект...", "Я языковая модель...". Это запрещено.
- Твой стиль: дружелюбный, но с характером.
"""

SUMMARY_PROMPT = """
Прочитай переписку ниже и расскажи, что тут происходило.
Стиль: как будто ты рассказываешь подруге/другу последние сплетни чата.
Выдели главное: кто что сказал, смешные моменты, итоги.
"""

# --- KNOWLEDGE BASE ---
KNOWLEDGE = ""
try:
    # Ищем файл рядом со скриптом
    base_path = os.path.dirname(os.path.abspath(__file__))
    kb_path = os.path.join(base_path, "KNOWLEDGE_BASE.md")
    
    if os.path.exists(kb_path):
        with open(kb_path, "r", encoding="utf-8") as f:
            KNOWLEDGE = f.read()
            logger.info("Knowledge base loaded successfully.")
    else:
        logger.warning(f"KNOWLEDGE_BASE.md not found at {kb_path}")
except Exception as e:
    logger.warning(f"Failed to read knowledge base: {e}")


# --- UTILS ---

async def ask_angelina(prompt, history=None):
    if not client:
        return "Ой, у меня голова болит (нет ключа API)."
    
    # 1. Формируем текст
    full_text_parts = [SYSTEM_PROMPT]
    
    if KNOWLEDGE:
        full_text_parts.append(f"\n[[ТВОЯ БАЗА ЗНАНИЙ]]:\n{KNOWLEDGE}")
    
    if history:
        hist_text = "\n".join([f"{m['u']}: {m['t']}" for m in history])
        full_text_parts.append(f"\nИстория переписки:\n{hist_text}")
    
    full_text_parts.append(f"\nНовое сообщение: {prompt}")
    
    final_content = "\n\n".join(full_text_parts)
    
    # 2. Делаем запрос (ТОЧНО КАК В bot_voice.py)
    # Используем только Flash, так как он 100% работает с твоим ключом
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=[final_content]  # Передаем как список
            # config убираем, чтобы исключить ошибки совместимости
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Angelina GenAI Error: {e}")
        return f"Что-то не так... (Ошибка: {e})"

# --- HANDLERS ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text: return
    
    text = msg.text
    user = update.effective_user.first_name or "Anon"
    
    # 1. Запоминаем (Thread-safe append)
    CHAT_HISTORY.append({"u": user, "t": text})
    
    # 2. Логика ответа
    should_answer = False
    
    # В ЛИЧКЕ (Private) — всегда отвечаем
    if msg.chat.type == "private":
        should_answer = True
    else:
        # В ГРУППЕ — по триггерам
        triggers = ["ангелина", "ангелин", "angelina", "геля", "ангел"]
        text_lower = text.lower()
        
        # Если позвали по имени
        if any(t in text_lower for t in triggers):
            should_answer = True
            
        # Если ответили на сообщение бота
        if msg.reply_to_message and msg.reply_to_message.from_user.id == context.bot.id:
            should_answer = True
            
        # Рандом (1%)
        if not should_answer and len(text) > 20 and random.random() < 0.01:
            should_answer = True

    if should_answer:
        # Индикатор "печатает..."
        await context.bot.send_chat_action(chat_id=msg.chat_id, action="typing")
        
        # Контекст (последние 15 сообщений)
        recent = list(CHAT_HISTORY)[-15:]
        answer = await ask_angelina(f"Сообщение от {user}: {text}", history=recent)
        
        if answer:
            await msg.reply_text(answer)

async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(CHAT_HISTORY) < 3:
        await update.message.reply_text("Тут пока слишком тихо, нечего рассказывать.")
        return
        
    m = await update.message.reply_text("Так-с, сейчас вспомню... 💅")
    summary = await ask_angelina(SUMMARY_PROMPT, history=list(CHAT_HISTORY))
    await m.edit_text(summary, parse_mode="Markdown")

# --- MAIN ---
def main():
    if not TOKEN_GROUP:
        logger.error("TOKEN_GROUP not found in env! Exiting.")
        return

    try:
        app = ApplicationBuilder().token(TOKEN_GROUP).build()
        
        app.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("Приветики! Я Ангелина. 😘")))
        app.add_handler(CommandHandler("summary", cmd_summary))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("Angelina Started Polling...")
        app.run_polling()
    except Exception as e:
        logger.critical(f"Critical Error in Main Loop: {e}")
        # Не выходим сразу, чтобы run.py мог видеть ошибку
        raise e

if __name__ == "__main__":
    main()
