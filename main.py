"""
CLI interface for WhisperX transcription pipeline.

Usage:
    python main.py input_file.mp4 --language ru
    python main.py videos/test.mkv -l en
"""

import argparse
import os
import time
from pathlib import Path

from core import Options, run_pipeline


def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()


def main():
    """Main CLI entry point."""
    load_env_file()

    parser = argparse.ArgumentParser(
        description="Transcription and diarization of audio/video files using WhisperX"
    )
    parser.add_argument(
        "input_file",
        type=Path,
        nargs="?",
        default=Path("videos/alawar.mkv"),
        help="Path to input file (mp4, mkv, mp3, wav). Default: videos/alawar.mkv",
    )
    parser.add_argument(
        "--language", "-l",
        type=str,
        default=None,
        help="Language code (ru, en, etc.). If not specified, auto-detect.",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="large-v3",
        choices=["large-v3", "medium", "small", "base", "tiny"],
        help="Whisper model size. Default: large-v3",
    )
    parser.add_argument(
        "--device", "-d",
        type=str,
        default="cuda",
        choices=["cuda", "cpu"],
        help="Device to use. Default: cuda",
    )
    parser.add_argument(
        "--compute-type",
        type=str,
        default="float16",
        choices=["float16", "int8", "float32"],
        help="Compute type. Default: float16",
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=4,
        help="Batch size for transcription. Default: 4",
    )
    parser.add_argument(
        "--no-diarize",
        action="store_true",
        help="Disable speaker diarization",
    )
    parser.add_argument(
        "--hf-token",
        type=str,
        default=None,
        help="HuggingFace token. If not provided, uses HF_TOKEN env variable.",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="data",
        help="Output root directory. Default: data",
    )

    args = parser.parse_args()

    # Get HF token
    hf_token = args.hf_token or os.getenv("HF_TOKEN", "")

    # Create options
    options = Options(
        model_name=args.model,
        device=args.device,
        compute_type=args.compute_type,
        language=args.language,
        batch_size=args.batch_size,
        diarize=not args.no_diarize,
        hf_token=hf_token if hf_token else None,
        output_root=args.output_dir,
    )

    # Run pipeline
    start_time = time.time()

    result = run_pipeline(
        input_path=str(args.input_file),
        options=options,
    )

    # Print final segments
    print("\n--- FINAL RESULT ---")
    for segment in result["result"]["segments"]:
        speaker = segment.get("speaker", "SPEAKER_??")
        start_time_seg = segment["start"]
        end_time_seg = segment["end"]
        text = segment["text"]
        print(f"[{start_time_seg:.2f}s - {end_time_seg:.2f}s] {speaker}: {text}")

    # Print summary
    elapsed = time.time() - start_time
    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = int(elapsed % 60)

    print(f"\n=== Total execution time: {hours:02}:{minutes:02}:{seconds:02} ===")
    print(f"Transcript saved to: {result['transcript_txt']}")


if __name__ == "__main__":
    main()
