from __future__ import annotations

import subprocess
from pathlib import Path

from .analysis import analyze_audio
from .compiler import compile_description, load_template
from .config import AppConfig
from .metadata import build_metadata_context
from .models import MediaSelection, PipelineResult, RenderResult
from .paths import ANIMATED_COVER_EXTENSIONS, ensure_directory


class PipelineError(RuntimeError):
    pass


def run_pipeline(
    config: AppConfig,
    beat: Path,
    cover: Path,
    artist_names: list[str],
    title: str,
    body: str,
    lastfm_api_key: str | None = None,
    lastfm_session_key: str | None = None,
) -> PipelineResult:
    ensure_directory(config.artifacts_dir)

    selection = MediaSelection(beat=beat, cover=cover, artist_names=artist_names)
    analysis = analyze_audio(selection.beat, config.analysis_confidence_threshold)
    metadata = build_metadata_context(artist_names, analysis, lastfm_api_key, lastfm_session_key)
    template = load_template(config.template_path)
    description = compile_description(template, metadata, title=title, body=body)
    rendered = render_video(config, selection, analysis)
    upload_id = None
    if config.publish_enabled:
        from .publisher import upload_to_youtube

        upload_id = upload_to_youtube(config, rendered.output_path, title, description, metadata)
    return PipelineResult(
        selection=selection,
        analysis=analysis,
        metadata=metadata,
        description=description,
        rendered_video=rendered.output_path,
        upload_id=upload_id,
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
