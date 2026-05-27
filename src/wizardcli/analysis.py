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
        import aubio
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise AudioAnalysisError("aubio is required for BPM detection") from exc

    samplerate = 44100
    hop_size = 512
    win_size = 1024
    src = aubio.source(str(path), samplerate, hop_size)  # type: ignore[attr-defined, call-arg]
    tempo = aubio.tempo("default", win_size, hop_size, samplerate)  # type: ignore[attr-defined, call-arg]

    while True:
        samples, read = src()
        tempo(samples)
        if read < hop_size:
            break

    bpm = float(tempo.get_bpm())
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
