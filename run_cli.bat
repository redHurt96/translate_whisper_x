@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   WhisperX - Командная строка (CLI)
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
echo Использование: python main.py [путь_к_файлу] [параметры]
echo Пример: python main.py videos/video.mp4 --language ru
echo.
echo Запуск с параметрами по умолчанию...
echo.

python main.py %*

echo.
pause
