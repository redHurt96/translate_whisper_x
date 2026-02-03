import whisperx
import os
import json
import subprocess
import shutil
import torch
import typing
import collections
import pathlib
import collections
import time
import argparse
from pathlib import Path

from format_transcript import format_transcript

from omegaconf import OmegaConf
from omegaconf.listconfig import ListConfig
from omegaconf.dictconfig import DictConfig
from omegaconf.base import ContainerMetadata, Metadata
from omegaconf.nodes import AnyNode
from pyannote.audio.core.task import Specifications, Problem, Resolution
from pyannote.audio.core.model import Introspection

from whisperx.diarize import DiarizationPipeline

torch.serialization.add_safe_globals([
    # torch
    torch.torch_version.TorchVersion,

    # omegaconf (часто внутри pyannote чекпоинтов)
    OmegaConf,
    ListConfig,
    DictConfig,
    ContainerMetadata,
    Metadata,
    AnyNode,

    # pyannote task types (встречались у тебя)
    Specifications,
    Problem,
    Resolution,

    # typing / builtins (встречались у тебя)
    typing.Any,
    list,
    dict,
    tuple,
    set,

    # типичные контейнеры/типы, которые иногда всплывают при weights_only
    pathlib.Path,
    collections.OrderedDict,
    collections.defaultdict,
    int,
    float, 
    str, 
    bool,

    Introspection,
])


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
device = "cuda"
compute_type = "float16"  # Тип вычислений, рекомендованный для GPU

# Включаем TensorFloat-32 для улучшения производительности на GPU
# (pyannote отключает это для воспроизводимости, но для обычного использования TF32 быстрее)
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# --- ПАРСИНГ АРГУМЕНТОВ ---
parser = argparse.ArgumentParser(
    description="Транскрипция и диаризация аудио/видео файлов с помощью WhisperX"
)
parser.add_argument(
    "input_file",
    type=Path,
    nargs="?",
    default=Path("videos/alawar.mkv"),
    help="Путь к входному файлу (mp4, mkv или mp3). По умолчанию: videos/alawar.mkv"
)
parser.add_argument(
    "--language", "-l",
    type=str,
    default="ru",
    help="Код языка аудио (ru, en, etc.). Указание языка ускоряет транскрипцию. По умолчанию: ru"
)
args = parser.parse_args()

# --- НАСТРОЙКИ ---
input_file = args.input_file
hf_token = os.getenv("HF_TOKEN", "")  # Токен берётся из переменной окружения HF_TOKEN
data_dir = Path("data")

# Засекаем время начала
start_time_total = time.time()


# --- ЭТАП 1: ПОДГОТОВКА АУДИОФАЙЛА И СТРУКТУРЫ ПАПОК ---
data_dir.mkdir(exist_ok=True)
output_dir = data_dir / input_file.stem
output_dir.mkdir(exist_ok=True)
audio_file = output_dir / "audio.mp3"

if not audio_file.exists():
    print(f"--- Подготовка аудио для '{input_file.name}' ---")
    video_formats = [".mp4", ".mkv"]
    if input_file.suffix.lower() in video_formats:
        print(f"Обнаружен видеофайл ({input_file.suffix}). Конвертация в MP3: {audio_file}")
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
        print(f"Неподдерживаемый формат файла: {input_file.suffix}. Ожидается .mp4, .mkv или .mp3")
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
    print(f"Транскрипция аудио (язык: {args.language})...")
    result = model.transcribe(audio, batch_size=4, language=args.language)
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

# --- ЭТАП 5: ФОРМАТИРОВАНИЕ ТРАНСКРИПТА ---
print("\n--- Этап 5: Форматирование ---")
# Определяем какой JSON использовать (диаризированный или выровненный)
final_json = diarized_cache if diarized_cache.is_file() else aligned_cache
format_transcript(final_json)

# Вывод общего времени выполнения
elapsed_time = time.time() - start_time_total
hours = int(elapsed_time // 3600)
minutes = int((elapsed_time % 3600) // 60)
seconds = int(elapsed_time % 60)
print(f"\n=== Общее время выполнения: {hours:02}:{minutes:02}:{seconds:02} ===")