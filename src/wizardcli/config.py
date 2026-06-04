from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import json
from typing import Optional


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


# Simple per-user credentials helper (file-based). This is intentionally
# minimal: it writes to ~/.wizardcli/wizardcli.json and reads `lastfm_api_key`.
# Prefer using the keyring or env var for stronger protection, but this keeps
# usage simple for local CLI users.

def _user_config_dir() -> Path:
    return Path(os.getenv("WIZARDCLI_CONFIG_DIR") or Path.home() / ".wizardcli")


def _config_file_path() -> Path:
    return _user_config_dir() / "wizardcli.json"


def _read_user_config() -> dict:
    p = _config_file_path()
    if not p.exists():
        return {}
    raw = p.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            text = raw.decode(encoding).strip().lstrip("\ufeff")
            while text.endswith("\\n"):
                text = text[:-2].rstrip()
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def _ensure_user_config_template() -> None:
    d = _user_config_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = _config_file_path()
    if p.exists():
        return
    template = {"lastfm_api_key": "", "lastfm_shared_secret": ""}
    with p.open("w", encoding="utf-8") as fh:
        json.dump(template, fh, indent=2)
    try:
        os.chmod(p, 0o600)
    except Exception:
        pass


def set_lastfm_api_key(key: str) -> None:
    _ensure_user_config_template()
    p = _config_file_path()
    data = _read_user_config()
    data["lastfm_api_key"] = key
    with p.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    try:
        os.chmod(p, 0o600)
    except Exception:
        # best-effort; Windows may raise or ignore
        pass


def get_lastfm_api_key() -> Optional[str]:
    _ensure_user_config_template()
    data = _read_user_config()
    return data.get("lastfm_api_key")


def get_lastfm_shared_secret() -> Optional[str]:
    _ensure_user_config_template()
    data = _read_user_config()
    return data.get("lastfm_shared_secret")


def set_lastfm_session(session_key: str, username: Optional[str] = None) -> None:
    _ensure_user_config_template()
    p = _config_file_path()
    data = _read_user_config()
    data["lastfm_session_key"] = session_key
    if username:
        data["lastfm_username"] = username
    with p.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    try:
        os.chmod(p, 0o600)
    except Exception:
        pass


def get_lastfm_session() -> Optional[str]:
    data = _read_user_config()
    return data.get("lastfm_session_key")
