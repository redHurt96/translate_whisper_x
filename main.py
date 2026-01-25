import whisperx
import os
import json
from pathlib import Path
import subprocess
import shutil
from whisperx.diarize import DiarizationPipeline

# Загрузка переменных окружения из .env файла (если существует)
env_file = Path(".env")
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# [Мнение] Для macOS лучше всего использовать CPU.
# Модели Apple Silicon (M1/M2/M3) могут использовать 'mps', но стабильность
# и производительность с whisperx могут варьироваться. CPU - надежный вариант.
device = "cpu"
compute_type = "int8"  # Тип вычислений, рекомендованный для CPU

# --- НАСТРОЙКИ ---
input_file = Path("videos/Как мониторить креативы и веб-воронки конкурентов [get.gt].mp4")  # <-- УКАЖИТЕ ПУТЬ К ВАШЕМУ MP4 ИЛИ MP3 ФАЙЛУ
hf_token = os.getenv("HF_TOKEN", "")  # Токен берётся из переменной окружения HF_TOKEN
data_dir = Path("data")


# --- ЭТАП 1: ПОДГОТОВКА АУДИОФАЙЛА И СТРУКТУРЫ ПАПОК ---
data_dir.mkdir(exist_ok=True)
output_dir = data_dir / input_file.stem
output_dir.mkdir(exist_ok=True)
audio_file = output_dir / "audio.mp3"

if not audio_file.exists():
    print(f"--- Подготовка аудио для '{input_file.name}' ---")
    if input_file.suffix.lower() == ".mp4":
        print(f"Обнаружен MP4 файл. Конвертация в MP3: {audio_file}")
        try:
            command = [
                "ffmpeg", "-i", str(input_file), "-vn",
                "-acodec", "libmp3lame", "-q:a", "2", str(audio_file)
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            print("Конвертация успешно завершена.")
        except FileNotFoundError:
            print("[Критическая ошибка] ffmpeg не найден. Убедитесь, что он установлен.")
            exit()
        except subprocess.CalledProcessError as e:
            print(f"[Критическая ошибка] Ошибка при конвертации: {e.stderr}")
            exit()
    elif input_file.suffix.lower() == ".mp3":
        print(f"Обнаружен MP3 файл. Копирование в: {audio_file}")
        shutil.copy(input_file, audio_file)
    else:
        print(f"Неподдерживаемый формат файла: {input_file.suffix}. Ожидается .mp4 или .mp3")
        exit()
else:
    print(f"Аудиофайл '{audio_file}' уже существует. Пропускаю подготовку.")


# --- ИНИЦИАЛИЗАЦИЯ КЕША ---
# [Факт] Теперь кеш хранится рядом с аудиофайлом, в своей папке.
cache_dir = output_dir / ".cache"
cache_dir.mkdir(exist_ok=True)
transcribed_cache = cache_dir / "transcribed.json"
aligned_cache = cache_dir / "aligned.json"
diarized_cache = cache_dir / "diarized.json"

result = None
# --- ПОПЫТКА ЗАГРУЗКИ ИЗ КЕША (ОТ ПОЛНОГО К ЧАСТИЧНОМУ) ---
if diarized_cache.is_file():
    print(f"Найден полный кеш (с диаризацией): {diarized_cache}. Загрузка результата...")
    with open(diarized_cache, 'r', encoding='utf-8') as f:
        result = json.load(f)
elif aligned_cache.is_file():
    print(f"Найден кеш после выравнивания: {aligned_cache}. Загрузка результата...")
    with open(aligned_cache, 'r', encoding='utf-8') as f:
        result = json.load(f)
elif transcribed_cache.is_file():
    print(f"Найден кеш после транскрипции: {transcribed_cache}. Загрузка результата...")
    with open(transcribed_cache, 'r', encoding='utf-8') as f:
        result = json.load(f)

# Проверка, что аудиофайл существует
if not os.path.exists(audio_file):
    print(f"Аудиофайл не найден: {audio_file}.")
    exit()

# Проверка токена Hugging Face
if hf_token == "YOUR_HF_TOKEN" or not hf_token:
    print("[Внимание] Для диаризации (определения спикеров) требуется токен Hugging Face. Определение спикеров будет пропущено.")
    diarize = False
else:
    diarize = True


# --- ОСНОВНАЯ ЛОГИКА ОБРАБОТКИ ---

# Шаг 1: Транскрипция
if result is None:
    print("\n--- Этап 2: Транскрипция ---")
    print("Кеш не найден. Начинаю полную обработку...")
    print("Загрузка модели Whisper...")
    model = whisperx.load_model("large-v3", device, compute_type=compute_type)
    print("Загрузка аудио...")
    audio = whisperx.load_audio(audio_file)
    print("Транскрипция аудио...")
    result = model.transcribe(audio, batch_size=4)
    print("Транскрипция завершена.")
    print(f"Сохранение кеша транскрипции: {transcribed_cache}")
    with open(transcribed_cache, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

# Проверяем, нужно ли выравнивание (если в сегментах нет ключа 'words')
needs_alignment = not result['segments'] or 'words' not in result['segments'][0]
if needs_alignment:
    print("\n--- Этап 3: Выравнивание ---")
    print("Выравнивание временных меток...")
    if 'audio' not in locals():
        audio = whisperx.load_audio(audio_file)
    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
    print("Выравнивание завершено.")
    print(f"Сохранение кеша после выравнивания: {aligned_cache}")
    with open(aligned_cache, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
else:
    print("Выравнивание уже выполнено (загружено из кеша).")


# Шаг 3: Диапизация (определение спикеров)
needs_diarization = diarize and ('speaker' not in result['segments'][0])
if needs_diarization:
    print("\n--- Этап 4: Диапизация ---")
    print("Определение спикеров (диаризация)...")
    if 'audio' not in locals():
        audio = whisperx.load_audio(audio_file)
    # [Факт] DiarizationPipeline находится в модуле whisperx.diarize.
    diarize_model = DiarizationPipeline(use_auth_token=hf_token, device=device)
    diarize_segments = diarize_model(audio)
    result = whisperx.assign_word_speakers(diarize_segments, result)
    print("Диаризация завершена.")
    print(f"Сохранение финального результата в кеш: {diarized_cache}")
    with open(diarized_cache, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
else:
    if diarize:
        print("Диаризация уже выполнена (загружена из кеша).")


# Вывод результата
print("\n--- ИТОГОВЫЙ РЕЗУЛЬТАТ ---")
for segment in result["segments"]:
    speaker = segment.get('speaker', 'SPEAKER_??')
    start_time = segment['start']
    end_time = segment['end']
    text = segment['text']
    print(f"[{start_time:.2f}s - {end_time:.2f}s] {speaker}: {text}")