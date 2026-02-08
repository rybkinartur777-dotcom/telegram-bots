
import asyncio
import os
import logging
import random
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

# Логирование
logging.basicConfig(
    format='%(asctime)s - [Angelina] - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CLIENT ---
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
- Если спрашивают время, погоду или факты — отвечай четко, но в разговорном стиле.
- Не используй фразы "Как искусственный интеллект...", "Я языковая модель...". Это запрещено.
- Пиши кратко, емко, иногда используй эмодзи.
- Твой стиль: дружелюбный, но с характером.
"""

SUMMARY_PROMPT = """
Прочитай переписку ниже и расскажи, что тут происходило.
Стиль: как будто ты рассказываешь подруге/другу последние сплетни чата.
Выдели главное: кто что сказал, смешные моменты, итоги.
"""

# --- UTILS ---

async def ask_angelina(prompt, history=None):
    if not client:
        return "Ой, у меня голова болит (нет ключа API)."
    
    try:
        content = []
        if history:
            hist_text = "\n".join([f"{m['u']}: {m['t']}" for m in history])
            content.append(f"История последних сообщений в чате:\n{hist_text}\n\n")
        
        content.append(prompt)
        
        # Flash - идеально для быстрой болтовни
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents="\n".join(content),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.8, # Живость
            )
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"GenAI Error: {e}")
        return "Что-то я подвисла... Повтори?"

# --- HANDLERS ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text: return
    
    text = msg.text
    user = update.effective_user.first_name
    
    # 1. Запоминаем (для саммари)
    CHAT_HISTORY.append({"u": user, "t": text})
    
    # 2. Триггеры (когда отвечать)
    should_answer = False
    
    # Имя (разные регистры)
    triggers = ["ангелина", "ангелин", "angelina", "геля"]
    text_lower = text.lower()
    
    if any(t in text_lower for t in triggers):
        should_answer = True
        
    # Реплай на сообщение бота
    if msg.reply_to_message and msg.reply_to_message.from_user.id == context.bot.id:
        should_answer = True
        
    # Рандом (редко, 2%)
    if not should_answer and len(text) > 15 and random.random() < 0.02:
        should_answer = True
        
    if should_answer:
        # Берем контекст (последние 15 сообщений)
        recent = list(CHAT_HISTORY)[-15:]
        answer = await ask_angelina(f"Сообщение от {user}: {text}", history=recent)
        if answer:
            await msg.reply_text(answer)

async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(CHAT_HISTORY) < 5:
        await update.message.reply_text("Да мы еще толком не общались, нечего рассказывать.")
        return
        
    m = await update.message.reply_text("Та-а-ак, дай вспомню... 💅")
    summary = await ask_angelina(SUMMARY_PROMPT, history=list(CHAT_HISTORY))
    await m.edit_text(summary)

# --- RUN ---
def main():
    if not TOKEN_GROUP:
        print("[Angelina] TOKEN_GROUP not found! I sleep.")
        return
        
    app = ApplicationBuilder().token(TOKEN_GROUP).build()
    
    app.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("Привет! Я Ангелина. 😘")))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("[Angelina] Woke up and ready to chat.")
    app.run_polling()

if __name__ == "__main__":
    main()
