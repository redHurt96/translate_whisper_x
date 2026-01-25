import argparse
import json
from pathlib import Path

def format_time(seconds: float) -> str:
    """Конвертирует время в секундах в формат [чч:мм:сс]."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{secs:02}"

def format_transcript(json_path: Path):
    """
    Форматирует JSON-файл с результатами диаризации в человекочитаемый
    текстовый файл (.txt).

    Args:
        json_path: Путь к JSON-файлу (например, diarized.json).
    """
    if not json_path.is_file():
        print(f"[Ошибка] Файл не найден: {json_path}")
        return

    # [Факт] Выходной файл будет сохранен в папку на уровень выше .cache,
    # то есть рядом с аудиофайлом. Например, data/my_video/transcript.txt
    output_txt_path = json_path.parent.parent / "transcript.txt"

    print(f"Чтение JSON-файла: {json_path}")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"[Критическая ошибка] Не удалось прочитать JSON-файл. Возможно, он поврежден: {json_path}")
        return

    lines = []
    if "segments" not in data:
        print("[Ошибка] В JSON-файле отсутствует ключ 'segments'.")
        return

    print("Форматирование сегментов...")
    for segment in data["segments"]:
        speaker = segment.get('speaker', 'SPEAKER_??')
        start = segment.get('start', 0.0)
        end = segment.get('end', 0.0)
        text = segment.get('text', '').strip()

        if not text:
            continue
        
        start_formatted = format_time(start)
        end_formatted = format_time(end)
        lines.append(f"[{start_formatted} - {end_formatted}] {speaker}: {text}")

    output_content = "\n".join(lines)
    
    print(f"Сохранение отформатированного текста в: {output_txt_path}")
    with open(output_txt_path, 'w', encoding='utf-8') as f:
        f.write(output_content)

    print("Форматирование завершено.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Форматирует JSON-результат от whisperx в человекочитаемый текстовый файл."
    )
    parser.add_argument(
        "json_file",
        type=Path,
        help="Путь к JSON-файлу с результатами (обычно это diarized.json).",
    )
    args = parser.parse_args()
    format_transcript(args.json_file)
