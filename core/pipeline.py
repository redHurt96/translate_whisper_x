"""
WhisperX transcription pipeline.

This module contains the main pipeline logic for transcribing, aligning,
and diarizing audio/video files using WhisperX.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional, Dict, Any

from .options import Options
from .safe_globals import register_safe_globals


def _log(msg: str, log_cb: Optional[Callable[[str], None]] = None):
    """Log a message, optionally via callback."""
    print(msg)
    if log_cb:
        log_cb(msg)


def _progress(value: float, progress_cb: Optional[Callable[[float], None]] = None):
    """Report progress (0.0 to 1.0), optionally via callback."""
    if progress_cb:
        progress_cb(value)


def format_time(seconds: float) -> str:
    """Convert seconds to [HH:MM:SS] format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{secs:02}"


def export_transcript(result: dict, output_path: Path, log_cb: Optional[Callable[[str], None]] = None) -> Path:
    """
    Export transcription result to a human-readable text file.

    Format: [start - end] SPEAKER_XX: text

    Args:
        result: Transcription result dictionary containing 'segments'
        output_path: Path to save the transcript.txt file
        log_cb: Optional logging callback

    Returns:
        Path to the created transcript file
    """
    _log(f"Exporting transcript to: {output_path}", log_cb)

    lines = []
    segments = result.get("segments", [])

    for segment in segments:
        speaker = segment.get("speaker", "SPEAKER_??")
        start = segment.get("start", 0.0)
        end = segment.get("end", 0.0)
        text = segment.get("text", "").strip()

        if not text:
            continue

        start_fmt = format_time(start)
        end_fmt = format_time(end)
        lines.append(f"[{start_fmt} - {end_fmt}] {speaker}: {text}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    _log(f"Transcript saved: {len(lines)} segments", log_cb)
    return output_path


def run_pipeline(
    input_path: str,
    options: Options,
    log_cb: Optional[Callable[[str], None]] = None,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> Dict[str, Any]:
    """
    Run the complete WhisperX transcription pipeline.

    Stages:
        1. Extract/prepare audio file
        2. Transcribe using WhisperX
        3. Align word-level timestamps
        4. Diarize speakers (if enabled and HF token provided)
        5. Export transcript.txt

    Args:
        input_path: Path to input file (mp4, mkv, mp3, wav)
        options: Pipeline configuration options
        log_cb: Optional callback for logging (receives log strings)
        progress_cb: Optional callback for progress (receives 0.0-1.0)

    Returns:
        Dictionary with paths to artifacts:
        - output_dir: Directory containing all outputs
        - audio_file: Path to extracted/copied audio
        - transcribed_json: Path to transcribed.json cache
        - aligned_json: Path to aligned.json cache
        - diarized_json: Path to diarized.json cache (or None)
        - transcript_txt: Path to final transcript.txt
    """
    # Register safe globals for torch deserialization
    register_safe_globals()

    import torch

    # Enable TensorFloat-32 for better GPU performance
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

    import whisperx
    from whisperx.diarize import DiarizationPipeline

    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    _progress(0.0, progress_cb)
    _log(f"Starting pipeline for: {input_file.name}", log_cb)

    # Setup directories
    data_dir = Path(options.output_root)
    data_dir.mkdir(exist_ok=True)
    output_dir = data_dir / input_file.stem
    output_dir.mkdir(exist_ok=True)
    cache_dir = output_dir / ".cache"
    cache_dir.mkdir(exist_ok=True)

    # Define paths
    audio_file = output_dir / "audio.mp3"
    transcribed_cache = cache_dir / "transcribed.json"
    aligned_cache = cache_dir / "aligned.json"
    diarized_cache = cache_dir / "diarized.json"
    transcript_txt = output_dir / "transcript.txt"

    # --- STAGE 1: Prepare audio file ---
    _log("--- Stage 1: Audio Preparation ---", log_cb)
    _progress(0.05, progress_cb)

    if not audio_file.exists():
        suffix = input_file.suffix.lower()
        video_formats = [".mp4", ".mkv"]

        if suffix in video_formats:
            _log(f"Detected video file ({suffix}). Converting to MP3...", log_cb)
            ffmpeg_cmd = options.ffmpeg_path or "ffmpeg"
            try:
                command = [
                    ffmpeg_cmd, "-i", str(input_file), "-vn",
                    "-acodec", "libmp3lame", "-q:a", "2", str(audio_file)
                ]
                subprocess.run(command, check=True, capture_output=True, text=True)
                _log("Audio conversion completed.", log_cb)
            except FileNotFoundError:
                raise RuntimeError("ffmpeg not found. Please install ffmpeg.")
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"ffmpeg error: {e.stderr}")

        elif suffix == ".mp3":
            _log(f"Detected MP3 file. Copying to: {audio_file}", log_cb)
            shutil.copy(input_file, audio_file)

        elif suffix == ".wav":
            _log(f"Detected WAV file. Converting to MP3...", log_cb)
            ffmpeg_cmd = options.ffmpeg_path or "ffmpeg"
            try:
                command = [
                    ffmpeg_cmd, "-i", str(input_file), "-vn",
                    "-acodec", "libmp3lame", "-q:a", "2", str(audio_file)
                ]
                subprocess.run(command, check=True, capture_output=True, text=True)
                _log("Audio conversion completed.", log_cb)
            except FileNotFoundError:
                raise RuntimeError("ffmpeg not found. Please install ffmpeg.")
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"ffmpeg error: {e.stderr}")

        else:
            raise ValueError(f"Unsupported file format: {suffix}. Expected: .mp4, .mkv, .mp3, .wav")
    else:
        _log(f"Audio file already exists: {audio_file}", log_cb)

    _progress(0.10, progress_cb)

    # --- Load from cache (most complete to least) ---
    result = None
    loaded_from = None

    if diarized_cache.is_file():
        _log(f"Loading from cache (diarized): {diarized_cache}", log_cb)
        with open(diarized_cache, "r", encoding="utf-8") as f:
            result = json.load(f)
        loaded_from = "diarized"
    elif aligned_cache.is_file():
        _log(f"Loading from cache (aligned): {aligned_cache}", log_cb)
        with open(aligned_cache, "r", encoding="utf-8") as f:
            result = json.load(f)
        loaded_from = "aligned"
    elif transcribed_cache.is_file():
        _log(f"Loading from cache (transcribed): {transcribed_cache}", log_cb)
        with open(transcribed_cache, "r", encoding="utf-8") as f:
            result = json.load(f)
        loaded_from = "transcribed"

    # Check diarization settings
    do_diarize = options.diarize and options.hf_token and options.hf_token.strip()
    if options.diarize and not do_diarize:
        _log("[Warning] Diarization requested but HF_TOKEN not provided. Skipping speaker detection.", log_cb)

    # --- STAGE 2: Transcription ---
    audio = None  # Will be loaded when needed

    if result is None:
        _log("--- Stage 2: Transcription ---", log_cb)
        _log("No cache found. Starting full processing...", log_cb)
        _log(f"Loading Whisper model: {options.model_name}...", log_cb)
        _progress(0.15, progress_cb)

        model = whisperx.load_model(
            options.model_name,
            options.device,
            compute_type=options.compute_type
        )

        _log("Loading audio...", log_cb)
        audio = whisperx.load_audio(str(audio_file))

        lang_str = options.language or "auto-detect"
        _log(f"Transcribing audio (language: {lang_str})...", log_cb)
        _progress(0.20, progress_cb)

        transcribe_kwargs = {"batch_size": options.batch_size}
        if options.language:
            transcribe_kwargs["language"] = options.language

        result = model.transcribe(audio, **transcribe_kwargs)

        _log("Transcription completed.", log_cb)
        _log(f"Saving transcription cache: {transcribed_cache}", log_cb)
        with open(transcribed_cache, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # Free model memory
        del model
        if options.device == "cuda":
            torch.cuda.empty_cache()

        loaded_from = "transcribed"

    _progress(0.50, progress_cb)

    # --- STAGE 3: Alignment ---
    needs_alignment = (
        not result.get("segments") or
        "words" not in result["segments"][0]
    )

    if needs_alignment:
        _log("--- Stage 3: Alignment ---", log_cb)
        _log("Aligning word-level timestamps...", log_cb)
        _progress(0.55, progress_cb)

        if audio is None:
            audio = whisperx.load_audio(str(audio_file))

        detected_language = result.get("language", options.language or "en")
        model_a, metadata = whisperx.load_align_model(
            language_code=detected_language,
            device=options.device
        )

        result = whisperx.align(
            result["segments"],
            model_a,
            metadata,
            audio,
            options.device,
            return_char_alignments=False
        )

        _log("Alignment completed.", log_cb)
        _log(f"Saving alignment cache: {aligned_cache}", log_cb)
        with open(aligned_cache, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # Free model memory
        del model_a
        if options.device == "cuda":
            torch.cuda.empty_cache()

        loaded_from = "aligned"
    else:
        _log("Alignment already done (loaded from cache).", log_cb)

    _progress(0.70, progress_cb)

    # --- STAGE 4: Diarization ---
    needs_diarization = (
        do_diarize and
        result.get("segments") and
        "speaker" not in result["segments"][0]
    )

    if needs_diarization:
        _log("--- Stage 4: Diarization ---", log_cb)
        _log("Detecting speakers...", log_cb)
        _progress(0.75, progress_cb)

        if audio is None:
            audio = whisperx.load_audio(str(audio_file))

        diarize_model = DiarizationPipeline(
            use_auth_token=options.hf_token,
            device=options.device
        )
        diarize_segments = diarize_model(audio)
        result = whisperx.assign_word_speakers(diarize_segments, result)

        _log("Diarization completed.", log_cb)
        _log(f"Saving diarization cache: {diarized_cache}", log_cb)
        with open(diarized_cache, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        loaded_from = "diarized"
    elif do_diarize:
        _log("Diarization already done (loaded from cache).", log_cb)

    _progress(0.90, progress_cb)

    # --- STAGE 5: Export transcript ---
    _log("--- Stage 5: Export Transcript ---", log_cb)
    export_transcript(result, transcript_txt, log_cb)

    _progress(1.0, progress_cb)
    _log("Pipeline completed successfully.", log_cb)

    return {
        "output_dir": str(output_dir),
        "audio_file": str(audio_file),
        "transcribed_json": str(transcribed_cache),
        "aligned_json": str(aligned_cache),
        "diarized_json": str(diarized_cache) if diarized_cache.is_file() else None,
        "transcript_txt": str(transcript_txt),
        "result": result,
    }


def clear_cache(input_path: str, output_root: str = "data") -> bool:
    """
    Clear cache for a specific input file.

    Removes the .cache directory and audio.* files in the output folder.

    Args:
        input_path: Path to the original input file
        output_root: Root data directory

    Returns:
        True if cache was cleared, False if nothing to clear
    """
    input_file = Path(input_path)
    output_dir = Path(output_root) / input_file.stem

    if not output_dir.exists():
        return False

    cleared = False

    # Remove cache directory
    cache_dir = output_dir / ".cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        cleared = True

    # Remove audio files
    for audio_file in output_dir.glob("audio.*"):
        audio_file.unlink()
        cleared = True

    return cleared
