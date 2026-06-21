from __future__ import annotations

import subprocess
from pathlib import Path

from .compiler import compile_description, load_template
from .config import AppConfig
from .metadata import build_metadata_context
from .models import DescriptionDraft, DescriptionInputs, MediaSelection, PipelineResult, RenderResult
from .paths import ANIMATED_COVER_EXTENSIONS, ensure_directory


class PipelineError(RuntimeError):
    pass


def run_pipeline(
    config: AppConfig,
    beat: Path,
    cover: Path,
    artist_names: list[str],
    descriptors: list[str] | None,
    title: str,
    body: str,
    lastfm_api_key: str | None = None,
    lastfm_session_key: str | None = None,
) -> PipelineResult:
    ensure_directory(config.artifacts_dir)

    inputs = DescriptionInputs(
        artist_names=artist_names,
        descriptors=descriptors or [],
        title=title,
    )
    draft = generate_description_draft(
        config,
        beat=beat,
        inputs=inputs,
        lastfm_api_key=lastfm_api_key,
        lastfm_session_key=lastfm_session_key,
        body_override=body,
    )
    selection = MediaSelection(
        beat=beat,
        cover=cover,
        artist_names=artist_names,
        query_terms=descriptors or [],
    )
    rendered = render_video(config, selection, draft.analysis)
    upload_id = None
    if config.publish_enabled:
        from .publisher import upload_to_youtube

        upload_id = upload_to_youtube(
            config,
            rendered.output_path,
            draft.title,
            draft.description,
            draft.metadata,
        )
    return PipelineResult(
        selection=selection,
        analysis=draft.analysis,
        metadata=draft.metadata,
        description=draft.description,
        rendered_video=rendered.output_path,
        upload_id=upload_id,
    )


def generate_description_draft(
    config: AppConfig,
    beat: Path,
    inputs: DescriptionInputs,
    lastfm_api_key: str | None = None,
    lastfm_session_key: str | None = None,
    body_override: str | None = None,
) -> DescriptionDraft:
    artist_names = _clean_terms(inputs.artist_names)
    descriptors = _clean_terms(inputs.descriptors)
    if not artist_names:
        raise PipelineError("Add at least one artist before generating a description.")

    metadata = build_metadata_context(
        artist_names,
        None,
        lastfm_api_key,
        lastfm_session_key,
        descriptors=descriptors,
    )
    title = _description_title(inputs, artist_names, descriptors)
    body = body_override if body_override is not None else _description_body(metadata)
    template = load_template(config.template_path)
    description = compile_description(template, metadata, title=title, body=body)
    return DescriptionDraft(
        inputs=DescriptionInputs(
            artist_names=artist_names,
            descriptors=descriptors,
            title=inputs.title.strip() if inputs.title and inputs.title.strip() else None,
        ),
        title=title,
        body=body,
        analysis=None,
        metadata=metadata,
        description=description,
    )


def render_video(config: AppConfig, selection: MediaSelection, analysis) -> RenderResult:
    output_path = config.artifacts_dir / f"{selection.beat.stem}_1440p.mp4"
    is_gif = selection.cover.suffix.lower() in ANIMATED_COVER_EXTENSIONS
    video_filter = (
        "scale=2560:1440:force_original_aspect_ratio=decrease,"
        "pad=2560:1440:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
    )

    command = ["ffmpeg", "-y"]
    if is_gif:
        command.extend(["-stream_loop", "-1"])
    else:
        command.extend(["-loop", "1"])

    command.extend(
        [
            "-i",
            str(selection.cover),
            "-i",
            str(selection.beat),
            "-shortest",
            "-vf",
            video_filter,
            "-c:v",
            "h264_videotoolbox",
            "-b:v",
            "20M",
            "-c:a",
            "aac",
            "-b:a",
            "320k",
            str(output_path),
        ]
    )
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise PipelineError("ffmpeg was not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise PipelineError(f"ffmpeg render failed for {selection.beat.name}") from exc

    return RenderResult(
        output_path=output_path,
        video_codec="h264_videotoolbox",
        audio_source=selection.beat,
        cover_source=selection.cover,
    )


def _clean_terms(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = " ".join(value.strip().split()) if value else ""
        key = text.lower()
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
    return cleaned


def _description_title(
    inputs: DescriptionInputs,
    artist_names: list[str],
    descriptors: list[str],
) -> str:
    if inputs.title and inputs.title.strip():
        return inputs.title.strip()
    if artist_names:
        return f"{artist_names[0]} type beat"
    if descriptors:
        return f"{descriptors[0]} type beat"
    return "type beat"


def _description_body(metadata) -> str:
    lines: list[str] = []
    if metadata.artists:
        lines.append(f"Artists: {', '.join(metadata.artists)}")
    if metadata.descriptors:
        lines.append(f"Descriptors: {', '.join(metadata.descriptors)}")
    if metadata.bpm is not None or metadata.key:
        details = []
        if metadata.bpm is not None:
            details.append(f"BPM: {metadata.bpm:.2f}")
        if metadata.key:
            details.append(f"Key: {metadata.key}")
        lines.append(" / ".join(details))
    if metadata.summary:
        lines.append("")
        lines.append(metadata.summary)
    return "\n".join(lines).strip()
