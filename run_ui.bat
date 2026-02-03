@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   WhisperX - Запуск веб-интерфейса (UI)
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ОШИБКА] Виртуальное окружение .venv не найдено!
    echo.
    echo Сначала запустите setup_win.bat для установки.
    echo.
    pause
    exit /b 1
)

echo Активация виртуального окружения...
call ".venv\Scripts\activate.bat"

echo.
echo UI откроется в браузере. Смотри консоль для URL.
echo Для остановки нажмите Ctrl+C
echo.

python ui_gradio.py

echo.
pause
