@echo off
chcp 65001 >nul
echo ========================================
echo Telegram Bot - Голосовые сообщения
echo ========================================
echo.

:check_python
echo Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден! Пожалуйста, установите Python 3.8+ с https://www.python.org
    pause
    exit /b 1
)
echo ✓ Python найден

:check_ffmpeg
echo.
echo Проверка ffmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo ⚠️  ffmpeg не найден в PATH
    echo Пожалуйста, установите ffmpeg:
    echo   1. Скачайте с https://ffmpeg.org/download.html
    echo   2. Распакуйте и добавьте папку bin в переменную PATH
    echo   3. Перезагрузитесь
    echo.
    set /p continue="Продолжить? (y/n): "
    if /i not "%continue%"=="y" exit /b 1
) else (
    echo ✓ ffmpeg найден
)

:install_deps
echo.
echo Установка зависимостей Python...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Ошибка при установке зависимостей
    pause
    exit /b 1
)
echo ✓ Зависимости установлены

:config
echo.
echo ========================================
echo ВАЖНО: Замените TOKEN в файле bot.py!
echo Получите токен у BotFather в Telegram
echo ========================================
echo.
set /p start_bot="Запустить бота? (y/n): "
if /i "%start_bot%"=="y" (
    echo.
    echo Запуск бота...
    python bot.py
) else (
    echo Для запуска бота выполните: python bot.py
)

pause
