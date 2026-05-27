from __future__ import annotations

from pathlib import Path

from wizardcli.config import DEFAULT_COVERS_DIR, DEFAULT_SONGS_DIR, default_config


def test_default_config_uses_drive_defaults(monkeypatch) -> None:
    monkeypatch.delenv("WIZARDCLI_SONGS_DIR", raising=False)
    monkeypatch.delenv("WIZARDCLI_COVERS_DIR", raising=False)

    config = default_config(root_dir=Path("C:/repo"))

    assert config.songs_dir == DEFAULT_SONGS_DIR
    assert config.covers_dir == DEFAULT_COVERS_DIR
    assert config.artifacts_dir == Path("C:/repo") / "artifacts"


def test_default_config_honors_environment_overrides(monkeypatch) -> None:
    monkeypatch.setenv("WIZARDCLI_SONGS_DIR", "D:/beats")
    monkeypatch.setenv("WIZARDCLI_COVERS_DIR", "D:/covers")

    config = default_config(root_dir=Path("C:/repo"))

    assert config.songs_dir == Path("D:/beats")
    assert config.covers_dir == Path("D:/covers")


def test_default_config_honors_explicit_overrides() -> None:
    config = default_config(
        root_dir=Path("C:/repo"),
        songs_dir=Path("E:/songs"),
        covers_dir=Path("E:/covers"),
    )

    assert config.songs_dir == Path("E:/songs")
    assert config.covers_dir == Path("E:/covers")
