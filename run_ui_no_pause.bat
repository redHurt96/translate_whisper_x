@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ОШИБКА] Виртуальное окружение .venv не найдено!
    echo Создайте: python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt
    timeout /t 5
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python ui_gradio.py
