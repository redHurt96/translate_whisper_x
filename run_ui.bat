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
    echo Создайте его командами:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo.
    echo Или через Poetry:
    echo   poetry install
    echo   poetry shell
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
