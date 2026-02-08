import asyncio
import os
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()

async def check_webhook(token_name, token_value):
    if not token_value:
        print(f"Skipping {token_name}: Token not found in .env")
        return

    try:
        bot = Bot(token=token_value)
        info = await bot.get_webhook_info()
        
        print(f"\n===== Checking: {token_name} =====")
        print(f"Bot Token: {token_value[:10]}...")
        print(f"URL: {info.url}")
        print(f"Pending update count: {info.pending_update_count}")
        if info.last_error_date:
            print(f"Last error date: {info.last_error_date}")
            print(f"Last error message: {info.last_error_message}")
        else:
            print("No recent errors reported by Telegram.")
            
        await bot.session.close()
    except Exception as e:
        print(f"Error checking {token_name}: {e}")

async def main():
    print("Checking Webhook Status for both bots...\n")
    tokens = {
        "TOKEN_MEDIA": os.getenv("TOKEN_MEDIA"),
        "TOKEN_VOICE": os.getenv("TOKEN_VOICE")
    }
    
    for name, value in tokens.items():
        await check_webhook(name, value)
        
if __name__ == "__main__":
    asyncio.run(main())
