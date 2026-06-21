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
class DescriptionInputs:
    artist_names: list[str]
    descriptors: list[str] = field(default_factory=list)
    title: str | None = None


@dataclass(frozen=True)
class MetadataContext:
    keywords: list[str]
    artists: list[str]
    summary: str
    descriptors: list[str] = field(default_factory=list)
    bpm: float | None = None
    key: str | None = None
    lastfm_enabled: bool = False
    lastfm_similar_artists: list[str] = field(default_factory=list)
    lastfm_discovered_descriptors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ModifierPool:
    guaranteed_artists: list[str]
    guaranteed_descriptors: list[str]
    similar_artists: list[str] = field(default_factory=list)
    discovered_descriptors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RenderResult:
    output_path: Path
    video_codec: str
    audio_source: Path
    cover_source: Path


@dataclass(frozen=True)
class DescriptionDraft:
    inputs: DescriptionInputs
    title: str
    body: str
    analysis: AudioAnalysisResult | None
    metadata: MetadataContext
    description: str


@dataclass(frozen=True)
class PipelineResult:
    selection: MediaSelection
    analysis: AudioAnalysisResult | None
    metadata: MetadataContext
    description: str
    rendered_video: Path
    upload_id: str | None = None
