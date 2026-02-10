
import subprocess
import time
import sys
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def run_bots():
    # Файлы для запуска (только голосовой бот)
    scripts = [
        (sys.executable, "-u", "bot_voice.py"),
        # (sys.executable, "-u", "bot_group.py"), # Ангелина выключена (по просьбе)
    ]

    processes = []
    
    # 1. Запуск
    for cmd_parts in scripts:
        script_name = cmd_parts[-1]
        logger.info(f"Запускаем {script_name}...")
        
        # Запускаем как Child Process
        p = subprocess.Popen(
            list(cmd_parts), 
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        processes.append((p, cmd_parts))

    # 2. Мониторинг (если упал голосовой — рестарт)
    try:
        while True:
            for i, (proc, cmd) in enumerate(processes):
                if proc.poll() is not None:  # Процесс умер
                    logger.warning(f"Процесс {cmd[-1]} упал. Перезапуск...")
                    new_proc = subprocess.Popen(
                        list(cmd),
                        stdout=sys.stdout,
                        stderr=sys.stderr
                    )
                    processes[i] = (new_proc, cmd)
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Остановка всех ботов...")
        for p, _ in processes:
            p.terminate()

if __name__ == "__main__":
    run_bots()
