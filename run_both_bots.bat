@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo Telegram Bot - Два независимых бота
echo ========================================
echo.

:check_python
echo [1/3] Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден! Пожалуйста, установите Python 3.8--
    pause
    exit /b 1
)
echo ✓ Python найден

:install_deps
echo.
echo [2/3] Установка зависимостей...
pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo ❌ Ошибка при установке зависимостей
    pause
    exit /b 1
)
echo ✓ Зависимости установлены

:config
echo.
echo [3/3] Проверка токенов...
echo.
echo ⚠️  ВАЖНО: Убедитесь что заменили токены в:
echo    • bot_voice.py (TOKEN_VOICE = "...")
echo    • bot_media.py (TOKEN_MEDIA = "...")
echo.
set /p continue="Токены заменены? (y/n): "
if /i not "!continue!"=="y" (
    echo ❌ Пожалуйста, отредактируйте токены и запустите заново
    pause
    exit /b 1
)

:start_bots
cls
echo ========================================
echo Запуск обоих ботов...
echo ========================================
echo.
echo 🎙️  Voice Bot запускается...
echo 🌐 Media Bot запускается...
echo.
echo Нажмите Ctrl+C чтобы остановить ботов
echo.

REM Запускаем оба бота в новых окнах
start "Voice Bot" cmd /k "python bot_voice.py"
timeout /t 2 /nobreak
start "Media Bot" cmd /k "python bot_media_local.py"

echo.
echo ✅ Оба бота запущены!
echo.
echo Вы можете:
echo • Использовать ботов в Telegram
echo • Закрыть это окно (ботов уберет Ctrl+C в их окнах)
echo.

pause
