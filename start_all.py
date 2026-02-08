
import asyncio
import subprocess
import sys
import os

async def run_script(script_name):
    """Запускает скрипт и следит за его выводом"""
    print(f"[Launcher] Starting {script_name}...")
    process = await asyncio.create_subprocess_exec(
        sys.executable, script_name,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Читаем вывод (чтобы видеть логи в Render)
    async def read_stream(stream, prefix):
        while True:
            line = await stream.readline()
            if not line: break
            print(f"[{prefix}] {line.decode().strip()}")

    await asyncio.gather(
        read_stream(process.stdout, script_name),
        read_stream(process.stderr, script_name)
    )

async def main():
    # Запускаем оба бота параллельно
    tasks = []
    
    # 1. Voice Bot (Web Server / Webhook)
    tasks.append(run_script("bot_voice.py"))
    
    # 2. Group Bot (Polling)
    # Важно: Поллинг нормально уживается с вебхуком другого бота, если токены разные.
    tasks.append(run_script("bot_group.py"))
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[Launcher] Stopping all bots...")
