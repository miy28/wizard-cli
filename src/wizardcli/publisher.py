from __future__ import annotations

from pathlib import Path

from .config import AppConfig
from .models import MetadataContext


class PublishError(RuntimeError):
    pass


def upload_to_youtube(config: AppConfig, video_path: Path, title: str, description: str, metadata: MetadataContext) -> str:
    raise PublishError("YouTube upload is not wired yet")
