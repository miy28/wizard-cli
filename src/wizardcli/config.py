from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SONGS_DIR = Path("G:/My Drive/studio/cooks")
DEFAULT_COVERS_DIR = Path("G:/My Drive/studio/covers")


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path
    songs_dir: Path
    covers_dir: Path
    artifacts_dir: Path
    template_path: Path
    client_secrets_path: Path
    oauth_token_path: Path
    youtube_upload_privacy: str = "private"
    analysis_confidence_threshold: float = 0.6
    publish_enabled: bool = False


def default_config(
    root_dir: Path | None = None,
    songs_dir: Path | str | None = None,
    covers_dir: Path | str | None = None,
) -> AppConfig:
    root = root_dir or Path.cwd()
    songs_root = Path(
        songs_dir
        or os.getenv("WIZARDCLI_SONGS_DIR")
        or DEFAULT_SONGS_DIR
    )
    covers_root = Path(
        covers_dir
        or os.getenv("WIZARDCLI_COVERS_DIR")
        or DEFAULT_COVERS_DIR
    )
    return AppConfig(
        root_dir=root,
        songs_dir=songs_root,
        covers_dir=covers_root,
        artifacts_dir=root / "artifacts",
        template_path=root / "template.md",
        client_secrets_path=root / "client_secrets.json",
        oauth_token_path=root / "token.json",
    )
