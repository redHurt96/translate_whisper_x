"""
Gradio Web UI for WhisperX Transcription Pipeline.

Run with: python ui_gradio.py
"""

import os
import queue
import threading
from pathlib import Path
from typing import Generator, Tuple, Optional

import gradio as gr

from core import Options, run_pipeline, clear_cache


def get_hf_token_from_env() -> str:
    """Load HF_TOKEN from environment or .env file."""
    # Try environment first
    token = os.getenv("HF_TOKEN", "")
    if token:
        return token

    # Try .env file
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    if key.strip() == "HF_TOKEN":
                        return value.strip()
    return ""


def process_file(
    file_obj,
    model_name: str,
    device: str,
    compute_type: str,
    diarize: bool,
    hf_token: str,
    language: str,
    batch_size: int,
) -> Generator[Tuple[str, Optional[str], str], None, None]:
    """
    Process uploaded file with WhisperX pipeline.

    Uses a queue and thread to stream logs without blocking the UI.

    Yields:
        Tuple of (logs_text, transcript_file_path, output_dir_path)
    """
    if file_obj is None:
        yield "Error: No file selected.", None, ""
        return

    # Get input path from uploaded file
    input_path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)

    # Use token from input or environment
    token = hf_token.strip() if hf_token.strip() else get_hf_token_from_env()

    # Parse language (empty = auto-detect)
    lang = language.strip() if language.strip() else None

    # Create options
    options = Options(
        model_name=model_name,
        device=device,
        compute_type=compute_type,
        language=lang,
        batch_size=batch_size,
        diarize=diarize,
        hf_token=token if token else None,
        output_root="data",
    )

    # Queue for log messages
    log_queue: queue.Queue[str] = queue.Queue()
    result_holder: dict = {"result": None, "error": None}

    def log_callback(msg: str):
        log_queue.put(msg)

    def run_in_thread():
        try:
            result = run_pipeline(
                input_path=input_path,
                options=options,
                log_cb=log_callback,
            )
            result_holder["result"] = result
        except Exception as e:
            result_holder["error"] = str(e)
            log_queue.put(f"[ERROR] {e}")

    # Start processing in background thread
    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()

    # Collect and stream logs
    logs = []
    while thread.is_alive() or not log_queue.empty():
        try:
            msg = log_queue.get(timeout=0.1)
            logs.append(msg)
            yield "\n".join(logs), None, ""
        except queue.Empty:
            continue

    # Thread finished - check result
    if result_holder["error"]:
        logs.append(f"\n[FAILED] Pipeline error: {result_holder['error']}")
        yield "\n".join(logs), None, ""
        return

    result = result_holder["result"]
    if result:
        transcript_path = result.get("transcript_txt")
        output_dir = result.get("output_dir", "")

        logs.append(f"\n[SUCCESS] Transcript saved to: {transcript_path}")
        logs.append(f"Output directory: {output_dir}")

        yield "\n".join(logs), transcript_path, output_dir
    else:
        logs.append("\n[FAILED] No result returned.")
        yield "\n".join(logs), None, ""


def clear_file_cache(file_obj) -> str:
    """Clear cache for the selected file."""
    if file_obj is None:
        return "No file selected."

    input_path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)

    if clear_cache(input_path, output_root="data"):
        stem = Path(input_path).stem
        return f"Cache cleared for: {stem}"
    else:
        stem = Path(input_path).stem
        return f"No cache found for: {stem}"


def create_ui() -> gr.Blocks:
    """Create the Gradio UI."""

    with gr.Blocks(title="WhisperX Transcription", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# WhisperX Transcription Pipeline")
        gr.Markdown("Upload a video/audio file to transcribe and optionally detect speakers.")

        with gr.Row():
            with gr.Column(scale=1):
                # Input file
                file_input = gr.File(
                    label="Upload File",
                    file_types=[".mp4", ".mkv", ".mp3", ".wav"],
                    type="filepath",
                )

                # Model settings
                model_dropdown = gr.Dropdown(
                    label="Model",
                    choices=["large-v3", "medium", "small", "base", "tiny"],
                    value="large-v3",
                )

                device_dropdown = gr.Dropdown(
                    label="Device",
                    choices=["cuda", "cpu"],
                    value="cuda",
                )

                compute_dropdown = gr.Dropdown(
                    label="Compute Type",
                    choices=["float16", "int8", "float32"],
                    value="float16",
                )

                # Diarization
                diarize_checkbox = gr.Checkbox(
                    label="Enable Diarization (Speaker Detection)",
                    value=True,
                )

                hf_token_input = gr.Textbox(
                    label="HuggingFace Token",
                    placeholder="Leave empty to use HF_TOKEN from .env",
                    type="password",
                )

                # Language
                language_input = gr.Textbox(
                    label="Language Code",
                    placeholder="Empty = auto-detect (e.g., ru, en, de)",
                    value="",
                )

                # Batch size
                batch_slider = gr.Slider(
                    label="Batch Size",
                    minimum=1,
                    maximum=32,
                    value=4,
                    step=1,
                )

                with gr.Row():
                    run_btn = gr.Button("Run", variant="primary")
                    clear_btn = gr.Button("Clear Cache", variant="secondary")

            with gr.Column(scale=1):
                # Logs output
                logs_output = gr.Textbox(
                    label="Logs",
                    lines=20,
                    max_lines=30,
                    interactive=False,
                )

                # Output path
                output_path_text = gr.Textbox(
                    label="Output Folder",
                    interactive=False,
                )

                # Download transcript
                transcript_file = gr.File(
                    label="Download Transcript",
                    interactive=False,
                )

        # Event handlers
        run_btn.click(
            fn=process_file,
            inputs=[
                file_input,
                model_dropdown,
                device_dropdown,
                compute_dropdown,
                diarize_checkbox,
                hf_token_input,
                language_input,
                batch_slider,
            ],
            outputs=[logs_output, transcript_file, output_path_text],
        )

        clear_btn.click(
            fn=clear_file_cache,
            inputs=[file_input],
            outputs=[logs_output],
        )

        # Footer
        gr.Markdown("---")
        gr.Markdown(
            "**Note:** For diarization (speaker detection), you need a HuggingFace token with access to "
            "[pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1). "
            "Set it in the field above or in the `.env` file as `HF_TOKEN=your_token`."
        )

    return demo


def main():
    """Launch the Gradio UI."""
    demo = create_ui()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
    )


if __name__ == "__main__":
    main()
