from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class MediaSelection:
    beat: Path
    cover: Path
    artist_names: list[str]
    query_terms: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AudioAnalysisResult:
    bpm: float
    key: str
    confidence: float


@dataclass(frozen=True)
class MetadataContext:
    keywords: list[str]
    artists: list[str]
    summary: str
    bpm: float | None = None
    key: str | None = None


@dataclass(frozen=True)
class RenderResult:
    output_path: Path
    video_codec: str
    audio_source: Path
    cover_source: Path


@dataclass(frozen=True)
class PipelineResult:
    selection: MediaSelection
    analysis: AudioAnalysisResult
    metadata: MetadataContext
    description: str
    rendered_video: Path
    upload_id: str | None = None
