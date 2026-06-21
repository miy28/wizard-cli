from __future__ import annotations

import math
from pathlib import Path

from .models import AudioAnalysisResult


class AudioAnalysisError(RuntimeError):
    pass


_KEY_NAMES = [
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
]


def analyze_audio(path: Path, confidence_threshold: float = 0.6) -> AudioAnalysisResult:
    bpm = _detect_bpm(path)
    key, confidence = _detect_key(path)
    result = AudioAnalysisResult(bpm=bpm, key=key, confidence=confidence)
    if result.confidence < confidence_threshold:
        raise AudioAnalysisError(
            f"Low confidence audio analysis for {path.name}: {result.confidence:.2f}"
        )
    return result


def _detect_bpm(path: Path) -> float:
    try:
        import librosa
        import numpy as np
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise AudioAnalysisError("librosa is required for BPM detection") from exc

    y, sr = librosa.load(path, mono=True)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.asarray(tempo).reshape(-1)[0])
    if not math.isfinite(bpm) or bpm <= 0:
        raise AudioAnalysisError(f"Unable to detect BPM for {path.name}")
    return bpm


def _detect_key(path: Path) -> tuple[str, float]:
    try:
        import librosa
        import numpy as np
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise AudioAnalysisError("librosa is required for key detection") from exc

    y, sr = librosa.load(path, mono=True)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)
    key_index = int(np.argmax(chroma_mean))
    confidence = float(np.max(chroma_mean) / (np.sum(chroma_mean) + 1e-9))
    key_name = _KEY_NAMES[key_index]
    return key_name, confidence
