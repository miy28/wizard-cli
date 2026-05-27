from pathlib import Path

import pytest

from wizardcli.paths import AUDIO_EXTENSIONS, COVER_EXTENSIONS
from wizardcli.paths import resolve_media_path


def test_resolve_media_path_by_name(tmp_path: Path) -> None:
    songs = tmp_path / "songs"
    songs.mkdir()
    target = songs / "2026-05-19.mp3"
    target.write_text("x", encoding="utf-8")

    resolved = resolve_media_path(songs, "2026-05-19.mp3")

    assert resolved == target


def test_resolve_media_path_with_allowed_extensions(tmp_path: Path) -> None:
    covers = tmp_path / "covers"
    covers.mkdir()
    target = covers / "cover.jpeg"
    target.write_text("x", encoding="utf-8")

    resolved = resolve_media_path(covers, "cover.jpeg", allowed_extensions=COVER_EXTENSIONS)

    assert resolved == target


def test_resolve_media_path_rejects_unsupported_extension(tmp_path: Path) -> None:
    songs = tmp_path / "songs"
    songs.mkdir()
    target = songs / "beat.txt"
    target.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError):
        resolve_media_path(songs, "beat.txt", allowed_extensions=AUDIO_EXTENSIONS)
