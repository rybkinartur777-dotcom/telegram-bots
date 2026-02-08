
import subprocess
import threading
import sys
import time

def run_script(script_name, prefix):
    """
    Запускает python скрипт в отдельном процессе и читает его вывод.
    Если скрипт падает, перезапускает его через 5 секунд.
    """
    while True:
        print(f"[{prefix}] Starting process...")
        try:
            # Запуск процесса
            process = subprocess.Popen(
                [sys.executable, "-u", script_name], # -u for unbuffered stdout
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace' # Игнорировать ошибки кодировки
            )
            
            # Чтение вывода в фоне (через потоки)
            def stream_reader(pipe, log_prefix):
                for line in iter(pipe.readline, ''):
                    print(f"[{log_prefix}] {line.strip()}")
                pipe.close()

            threading.Thread(target=stream_reader, args=(process.stdout, prefix), daemon=True).start()
            threading.Thread(target=stream_reader, args=(process.stderr, prefix + " ERROR"), daemon=True).start()
            
            # Ждем завершения
            process.wait()
            
            print(f"[{prefix}] Process exited with code {process.returncode}. Restarting in 5s...")
            time.sleep(5)
            
        except Exception as e:
            print(f"[{prefix}] Launcher Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # Запускаем два потока, каждый следит за своим ботом
    t1 = threading.Thread(target=run_script, args=("bot_voice.py", "VoiceBot"))
    t2 = threading.Thread(target=run_script, args=("bot_group.py", "Angelina"))
    
    t1.start()
    t2.start()
    
    # Главный поток просто ждет вечность
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping all bots...")
