from __future__ import annotations

from pathlib import Path

from wizardcli import config as config_module
from wizardcli.config import (
    DEFAULT_COVERS_DIR,
    DEFAULT_SONGS_DIR,
    default_config,
    get_lastfm_api_key,
    get_lastfm_shared_secret,
)


def test_default_config_uses_windows_drive_defaults(monkeypatch) -> None:
    monkeypatch.delenv("WIZARDCLI_SONGS_DIR", raising=False)
    monkeypatch.delenv("WIZARDCLI_COVERS_DIR", raising=False)
    monkeypatch.setattr(config_module.platform, "system", lambda: "Windows")

    config = default_config(root_dir=Path("C:/repo"))

    assert config.songs_dir == DEFAULT_SONGS_DIR
    assert config.covers_dir == DEFAULT_COVERS_DIR
    assert config.artifacts_dir == Path("C:/repo") / "artifacts"


def test_default_config_detects_macos_google_drive(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("WIZARDCLI_SONGS_DIR", raising=False)
    monkeypatch.delenv("WIZARDCLI_COVERS_DIR", raising=False)
    monkeypatch.setattr(config_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(config_module.Path, "home", lambda: tmp_path)
    drive_root = tmp_path / "Library/CloudStorage/GoogleDrive-user@example.com/My Drive"
    songs = drive_root / "studio/cooks"
    covers = drive_root / "studio/covers"
    songs.mkdir(parents=True)
    covers.mkdir(parents=True)

    config = default_config(root_dir=tmp_path)

    assert config.songs_dir == songs
    assert config.covers_dir == covers


def test_default_config_uses_local_fallback_on_other_platforms(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("WIZARDCLI_SONGS_DIR", raising=False)
    monkeypatch.delenv("WIZARDCLI_COVERS_DIR", raising=False)
    monkeypatch.setattr(config_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(config_module.Path, "home", lambda: tmp_path)

    config = default_config(root_dir=tmp_path)

    assert config.songs_dir == tmp_path / "Music/wizard-cli/songs"
    assert config.covers_dir == tmp_path / "Music/wizard-cli/covers"


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


def test_lastfm_getters_do_not_create_user_config(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "missing-config"
    monkeypatch.setenv("WIZARDCLI_CONFIG_DIR", str(config_dir))

    assert get_lastfm_api_key() is None
    assert get_lastfm_shared_secret() is None
    assert not config_dir.exists()
