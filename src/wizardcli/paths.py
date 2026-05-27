from __future__ import annotations

from pathlib import Path


AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".aif",
    ".aiff",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
}

COVER_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}

ANIMATED_COVER_EXTENSIONS = {".gif", ".webp"}


def resolve_media_path(
    base_dir: Path,
    value: str | Path,
    allowed_extensions: set[str] | None = None,
) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() and candidate.exists() and candidate.is_file():
        return _validate_extension(candidate, allowed_extensions)

    direct = base_dir / candidate
    if direct.exists() and direct.is_file():
        return _validate_extension(direct, allowed_extensions)

    if candidate.suffix:
        matches = list(base_dir.rglob(candidate.name))
        if matches:
            return _validate_extension(matches[0], allowed_extensions)

    matches = [path for path in base_dir.rglob("*") if path.is_file() and path.name == candidate.name]
    if matches:
        return _validate_extension(matches[0], allowed_extensions)

    raise FileNotFoundError(f"Could not resolve {value!s} under {base_dir}")


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_extension(path: Path, allowed_extensions: set[str] | None) -> Path:
    if not allowed_extensions:
        return path

    suffix = path.suffix.lower()
    if suffix in allowed_extensions:
        return path

    allowed = ", ".join(sorted(allowed_extensions))
    raise ValueError(f"Unsupported file type '{suffix or '<none>'}' for {path.name}. Allowed: {allowed}")
