
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
Ты находишься в чате telegram.
Твоя задача: общаться как живой человек, подруга.
- Ты можешь шутить, сарказмировать (по-доброму).
- Если спрашивают что-то умное — отвечай как эксперт.
- Не используй фразы "Как искусственный интеллект".
- Твой стиль: дружелюбный, но с характером.
"""

# --- KNOWLEDGE BASE ---
KNOWLEDGE = ""
try:
    base_path = os.path.dirname(os.path.abspath(__file__))
    kb_path = os.path.join(base_path, "KNOWLEDGE_BASE.md")
    if os.path.exists(kb_path):
        with open(kb_path, "r", encoding="utf-8") as f:
            KNOWLEDGE = f.read()
            logger.info("Knowledge base loaded.")
except Exception as e:
    logger.warning(f"No knowledge base: {e}")


# --- UTILS ---

async def ask_angelina(prompt, history=None):
    """
    Запрос к Gemini. Максимально простой и надежный (как в voice bot).
    """
    if not client:
        return "Ой, у меня голова болит (нет ключа API)."
    
    # 1. Собираем весь текст в один большой кусок (Prompt Engineering)
    # Это самый надежный способ для всех моделей.
    
    full_text = f"{SYSTEM_PROMPT}\n\n"
    
    if KNOWLEDGE:
        full_text += f"[[ТВОЯ БАЗА ЗНАНИЙ]]:\n{KNOWLEDGE}\n\n"
    
    if history:
        hist_text = "\n".join([f"{m['u']}: {m['t']}" for m in history])
        full_text += f"История переписки:\n{hist_text}\n\n"
    
    full_text += f"Новое сообщение: {prompt}"
    
    # 2. Отправляем запрос
    # Используем 'gemini-1.5-flash' так как он проверен и работает.
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[full_text],
            # config не используем, чтобы избежать ошибок версий
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"GenAI Request Failed: {e}")
        return f"Что-то пошло не так... (Error: {e})"

# --- HANDLERS ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text: return
    
    text = msg.text
    user = update.effective_user.first_name or "Anon"
    
    # 1. Запоминаем
    CHAT_HISTORY.append({"u": user, "t": text})
    
    # 2. Решаем, отвечать или нет
    should_answer = False
    
    # В ЛИЧКЕ — всегда
    if msg.chat.type == "private":
        should_answer = True
    else:
        # В ГРУППЕ — по имени или реплаю
        triggers = ["ангелина", "ангелин", "angelina", "геля"]
        if any(t in text.lower() for t in triggers):
            should_answer = True
            
        if msg.reply_to_message and msg.reply_to_message.from_user.id == context.bot.id:
            should_answer = True
            
        # Рандом 1%
        if not should_answer and len(text) > 20 and random.random() < 0.01:
            should_answer = True

    if should_answer:
        await context.bot.send_chat_action(chat_id=msg.chat_id, action="typing")
        
        # Контекст: последние 10 сообщений
        recent = list(CHAT_HISTORY)[-10:]
        answer = await ask_angelina(f"Сообщение от {user}: {text}", history=recent)
        
        if answer:
            await msg.reply_text(answer)

async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = await update.message.reply_text("Читаю переписку... 🧐")
    prompt = "Прочитай историю выше и сделай краткий смешной пересказ (саммери) того, что обсуждали."
    summary = await ask_angelina(prompt, history=list(CHAT_HISTORY))
    await m.edit_text(summary)

from telegram.error import Conflict, NetworkError

# --- MAIN ---
def main():
    if not TOKEN_GROUP:
        logger.error("TOKEN_GROUP not set.")
        return

    while True:
        try:
            app = ApplicationBuilder().token(TOKEN_GROUP).build()
            
            app.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("Привет! Я Ангелина.")))
            app.add_handler(CommandHandler("summary", cmd_summary))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            
            logger.info("Angelina Started Polling...")
            # drop_pending_updates=True помогает избежать глюков при рестарте
            # allowed_updates=["message"] экономит трафик
            app.run_polling(drop_pending_updates=True, allowed_updates=["message"])
            
        except Conflict:
            logger.warning("Conflict error (another bot instance is running). Waiting 10s...")
            import time
            time.sleep(10)
        except NetworkError:
            logger.warning("Network error. Retrying in 5s...")
            import time
            time.sleep(5)
        except Exception as e:
            logger.critical(f"Critical Main Error: {e}")
            import time
            time.sleep(10) # Ждем перед рестартом, чтобы не спамить логами


if __name__ == "__main__":
    main()
