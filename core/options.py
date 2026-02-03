"""Options dataclass for WhisperX pipeline configuration."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Options:
    """Configuration options for the WhisperX transcription pipeline."""

    # Model settings
    model_name: str = "large-v3"
    device: str = "cuda"
    compute_type: str = "float16"
    language: Optional[str] = None  # None = auto-detect
    batch_size: int = 4

    # Processing settings
    diarize: bool = True
    hf_token: Optional[str] = None

    # Paths
    output_root: str = "data"
    ffmpeg_path: Optional[str] = None  # None = use system ffmpeg

    def to_dict(self) -> dict:
        """Convert options to dictionary."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "compute_type": self.compute_type,
            "language": self.language,
            "batch_size": self.batch_size,
            "diarize": self.diarize,
            "hf_token": self.hf_token,
            "output_root": self.output_root,
            "ffmpeg_path": self.ffmpeg_path,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Options":
        """Create Options from dictionary."""
        return cls(
            model_name=d.get("model_name", "large-v3"),
            device=d.get("device", "cuda"),
            compute_type=d.get("compute_type", "float16"),
            language=d.get("language"),
            batch_size=d.get("batch_size", 4),
            diarize=d.get("diarize", True),
            hf_token=d.get("hf_token"),
            output_root=d.get("output_root", "data"),
            ffmpeg_path=d.get("ffmpeg_path"),
        )
