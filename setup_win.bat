@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ============================================
::   WhisperX - Windows Installer
::   Работает на чистом ПК без Python/ffmpeg
:: ============================================

cd /d "%~dp0"

echo.
echo ========================================
echo   WhisperX - Установка для Windows
echo ========================================
echo.

:: ============================================
:: 1. Проверка Python 3.12
:: ============================================

set "PY_CMD="
set "PY_VERSION="

:: Попробуем py -3.12
py -3.12 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=py -3.12"
    for /f "tokens=2" %%v in ('py -3.12 --version 2^>^&1') do set "PY_VERSION=%%v"
    goto :python_found
)

:: Попробуем python
python --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VERSION=%%v"
    echo !PY_VERSION! | findstr /C:"3.12" >nul
    if !errorlevel! equ 0 (
        set "PY_CMD=python"
        goto :python_found
    )
)

:: Попробуем python3
python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2" %%v in ('python3 --version 2^>^&1') do set "PY_VERSION=%%v"
    echo !PY_VERSION! | findstr /C:"3.12" >nul
    if !errorlevel! equ 0 (
        set "PY_CMD=python3"
        goto :python_found
    )
)

:: Python 3.12 не найден
echo [ОШИБКА] Python 3.12 не найден!
echo.

:: Проверим наличие winget
winget --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Winget доступен. Выполните команду для установки Python 3.12:
    echo.
    echo   winget install Python.Python.3.12
    echo.
    echo После установки ПЕРЕЗАПУСТИТЕ терминал и снова запустите setup_win.bat
) else (
    echo Winget не найден.
    echo.
    echo Установите Python 3.12 вручную:
    echo   1. Скачайте с https://www.python.org/downloads/
    echo   2. При установке ОБЯЗАТЕЛЬНО отметьте "Add Python to PATH"
    echo   3. Перезапустите терминал и снова запустите setup_win.bat
)
echo.
pause
exit /b 1

:python_found
echo [OK] Python найден: %PY_CMD% (%PY_VERSION%)
echo.

:: ============================================
:: 2. Проверка pip
:: ============================================

%PY_CMD% -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] pip не найден, пробуем установить через ensurepip...
    %PY_CMD% -m ensurepip --upgrade >nul 2>&1

    %PY_CMD% -m pip --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ОШИБКА] Не удалось установить pip!
        echo.
        echo Попробуйте переустановить Python с официального сайта python.org
        echo Убедитесь, что при установке включены pip и venv
        echo.
        pause
        exit /b 1
    )
)
echo [OK] pip доступен
echo.

:: ============================================
:: 3. Проверка venv
:: ============================================

%PY_CMD% -m venv --help >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Модуль venv недоступен!
    echo.
    echo Переустановите Python 3.12 с python.org
    echo При установке убедитесь, что компонент venv включен
    echo.
    pause
    exit /b 1
)
echo [OK] venv доступен
echo.

:: ============================================
:: 4. Проверка ffmpeg
:: ============================================

where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo ========================================
    echo [WARNING] ffmpeg не найден!
    echo ========================================
    echo.
    echo Без ffmpeg не будет работать конвертация mp4/mkv/webm.
    echo Для работы только с mp3/wav можно продолжить без него.
    echo.

    winget --version >nul 2>&1
    if !errorlevel! equ 0 (
        echo Для установки ffmpeg через winget выполните:
        echo.
        echo   winget install ffmpeg
        echo.
    ) else (
        echo Для установки ffmpeg:
        echo   1. Скачайте с https://ffmpeg.org/download.html
        echo   2. Распакуйте архив
        echo   3. Добавьте папку bin в системный PATH
        echo   4. Проверьте: ffmpeg -version
        echo.
    )
    echo Установка продолжится без ffmpeg...
    echo.
) else (
    echo [OK] ffmpeg найден
    echo.
)

:: ============================================
:: 5. Выбор режима CPU/GPU
:: ============================================

echo ========================================
echo   Выберите режим вычислений
echo ========================================
echo.
echo   1) CPU (работает везде)
echo   2) GPU NVIDIA (требует CUDA)
echo.

:choose_mode
set /p "MODE_CHOICE=Введите номер (1 или 2): "
if "%MODE_CHOICE%"=="1" (
    set "MODE=CPU"
    goto :mode_selected
)
if "%MODE_CHOICE%"=="2" (
    set "MODE=GPU"
    goto :mode_selected
)
echo Неверный ввод. Введите 1 или 2.
goto :choose_mode

:mode_selected
echo.
echo Выбран режим: %MODE%
echo.

:: Проверка nvidia-smi для GPU
if "%MODE%"=="GPU" (
    nvidia-smi >nul 2>&1
    if !errorlevel! neq 0 (
        echo ========================================
        echo [WARNING] nvidia-smi не найден!
        echo ========================================
        echo.
        echo Драйвер NVIDIA не обнаружен.
        echo GPU режим может не работать без драйверов NVIDIA.
        echo.
        echo Если у вас нет GPU NVIDIA, выберите режим CPU.
        echo.
        set /p "CONTINUE_GPU=Продолжить установку GPU версии? (y/n): "
        if /i "!CONTINUE_GPU!" neq "y" (
            set "MODE=CPU"
            echo.
            echo Переключено на CPU режим.
            echo.
        )
    ) else (
        echo [OK] NVIDIA драйвер обнаружен
        echo.
    )
)

:: ============================================
:: 6. Создание и активация venv
:: ============================================

if not exist ".venv\Scripts\python.exe" (
    echo Создание виртуального окружения...
    %PY_CMD% -m venv .venv
    if !errorlevel! neq 0 (
        echo [ОШИБКА] Не удалось создать виртуальное окружение!
        pause
        exit /b 1
    )
    echo [OK] Виртуальное окружение создано
    echo.
) else (
    echo [OK] Виртуальное окружение уже существует
    echo.
)

echo Активация виртуального окружения...
call ".venv\Scripts\activate.bat"
echo.

:: Обновление pip/setuptools/wheel
echo Обновление pip, setuptools, wheel...
python -m pip install -U pip setuptools wheel >nul 2>&1
echo [OK] Инструменты обновлены
echo.

:: ============================================
:: 7. Установка зависимостей
:: ============================================

echo ========================================
echo   Установка зависимостей
echo ========================================
echo.

:: 7.1 Base dependencies
if exist "requirements.base.txt" (
    echo Установка базовых зависимостей...
    pip install -r requirements.base.txt
    if !errorlevel! neq 0 (
        echo [ОШИБКА] Не удалось установить базовые зависимости!
        pause
        exit /b 1
    )
    echo [OK] Базовые зависимости установлены
    echo.
) else (
    echo [WARNING] requirements.base.txt не найден, пропускаем...
    echo.
)

:: 7.2 PyTorch
echo Установка PyTorch (%MODE% версия)...
echo Это может занять несколько минут...
echo.

if "%MODE%"=="CPU" (
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
) else (
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
)

if !errorlevel! neq 0 (
    echo [ОШИБКА] Не удалось установить PyTorch!
    pause
    exit /b 1
)
echo [OK] PyTorch установлен
echo.

:: ============================================
:: 8. Валидация torch и fallback
:: ============================================

echo Проверка PyTorch...
echo.

:: Получим версию torch и статус CUDA
for /f "delims=" %%i in ('python -c "import torch; print(torch.__version__)" 2^>^&1') do set "TORCH_VER=%%i"
for /f "delims=" %%i in ('python -c "import torch; print(torch.cuda.is_available())" 2^>^&1') do set "CUDA_AVAILABLE=%%i"

echo PyTorch версия: %TORCH_VER%
echo CUDA доступна: %CUDA_AVAILABLE%
echo.

if "%MODE%"=="GPU" (
    if "%CUDA_AVAILABLE%"=="False" (
        echo ========================================
        echo [WARNING] CUDA недоступна!
        echo ========================================
        echo.
        echo Вы выбрали GPU режим, но CUDA не работает.
        echo Возможные причины:
        echo   - Нет видеокарты NVIDIA
        echo   - Не установлены драйверы NVIDIA
        echo   - Не установлен CUDA Toolkit
        echo.
        echo   1) Переустановить PyTorch для CPU (рекомендуется)
        echo   2) Оставить как есть
        echo.

        :choose_fallback
        set /p "FALLBACK_CHOICE=Выберите (1 или 2): "
        if "!FALLBACK_CHOICE!"=="1" (
            echo.
            echo Переустановка PyTorch для CPU...
            pip uninstall -y torch torchvision torchaudio >nul 2>&1
            pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

            if !errorlevel! neq 0 (
                echo [ОШИБКА] Не удалось переустановить PyTorch!
                pause
                exit /b 1
            )

            set "MODE=CPU"
            echo [OK] PyTorch переустановлен для CPU
            echo.

            :: Проверка после переустановки
            for /f "delims=" %%i in ('python -c "import torch; print(torch.__version__)" 2^>^&1') do set "TORCH_VER=%%i"
            for /f "delims=" %%i in ('python -c "import torch; print(torch.cuda.is_available())" 2^>^&1') do set "CUDA_AVAILABLE=%%i"
            echo PyTorch версия: !TORCH_VER!
            echo CUDA доступна: !CUDA_AVAILABLE!
            echo.
        ) else if "!FALLBACK_CHOICE!"=="2" (
            echo.
            echo Оставлено без изменений. GPU режим может не работать.
            echo.
        ) else (
            echo Неверный ввод. Введите 1 или 2.
            goto :choose_fallback
        )
    ) else (
        echo [OK] CUDA доступна, GPU режим активен
        echo.
    )
)

:: ============================================
:: 9. Настройка .env
:: ============================================

echo Настройка .env файла...
echo.

:: Создаем .env если не существует
if not exist ".env" (
    echo # WhisperX Configuration > .env
    echo # Добавьте ваш HuggingFace токен ниже (нужен для диаризации) >> .env
    echo # HF_TOKEN=hf_your_token_here >> .env
    echo. >> .env
)

:: Функция обновления/добавления ключа в .env
:: Используем временный файл для безопасного редактирования

set "ENV_TEMP=.env.tmp"

:: Определяем значения в зависимости от режима
if "%MODE%"=="CPU" (
    set "NEW_DEVICE=cpu"
    set "NEW_COMPUTE=int8"
    set "NEW_BATCH=4"
) else (
    set "NEW_DEVICE=cuda"
    set "NEW_COMPUTE=float16"
    set "NEW_BATCH=8"
)

:: Читаем текущий .env и обновляем/добавляем ключи
set "FOUND_DEVICE=0"
set "FOUND_COMPUTE=0"
set "FOUND_BATCH=0"

if exist "%ENV_TEMP%" del "%ENV_TEMP%"

for /f "usebackq tokens=* delims=" %%a in (".env") do (
    set "LINE=%%a"

    :: Проверяем DEVICE
    echo !LINE! | findstr /B /C:"DEVICE=" >nul
    if !errorlevel! equ 0 (
        echo DEVICE=!NEW_DEVICE!>> "%ENV_TEMP%"
        set "FOUND_DEVICE=1"
    ) else (
        :: Проверяем COMPUTE_TYPE
        echo !LINE! | findstr /B /C:"COMPUTE_TYPE=" >nul
        if !errorlevel! equ 0 (
            echo COMPUTE_TYPE=!NEW_COMPUTE!>> "%ENV_TEMP%"
            set "FOUND_COMPUTE=1"
        ) else (
            :: Проверяем BATCH_SIZE
            echo !LINE! | findstr /B /C:"BATCH_SIZE=" >nul
            if !errorlevel! equ 0 (
                echo BATCH_SIZE=!NEW_BATCH!>> "%ENV_TEMP%"
                set "FOUND_BATCH=1"
            ) else (
                :: Сохраняем строку как есть
                echo !LINE!>> "%ENV_TEMP%"
            )
        )
    )
)

:: Добавляем отсутствующие ключи
if "%FOUND_DEVICE%"=="0" echo DEVICE=%NEW_DEVICE%>> "%ENV_TEMP%"
if "%FOUND_COMPUTE%"=="0" echo COMPUTE_TYPE=%NEW_COMPUTE%>> "%ENV_TEMP%"
if "%FOUND_BATCH%"=="0" echo BATCH_SIZE=%NEW_BATCH%>> "%ENV_TEMP%"

:: Заменяем .env
move /y "%ENV_TEMP%" ".env" >nul 2>&1

echo [OK] .env настроен (DEVICE=%NEW_DEVICE%, COMPUTE_TYPE=%NEW_COMPUTE%, BATCH_SIZE=%NEW_BATCH%)
echo.

:: ============================================
:: 10. Завершение
:: ============================================

echo ========================================
echo   Установка завершена!
echo ========================================
echo.
echo Режим: %MODE%
echo PyTorch: %TORCH_VER%
echo CUDA: %CUDA_AVAILABLE%
echo.

where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] ffmpeg не установлен - mp4/mkv не будут работать
    echo.
)

echo Следующие шаги:
echo   1. Добавьте HF_TOKEN в файл .env (нужен для диаризации)
echo   2. Запустите run_ui.bat для веб-интерфейса
echo   3. Или run_cli.bat для командной строки
echo.
echo Документация: README.md
echo.

pause
exit /b 0
