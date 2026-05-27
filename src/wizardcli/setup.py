from __future__ import annotations

import json
import shutil
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests


@dataclass
class SetupResult:
    python_installed: bool
    mpv_installed: bool
    mpv_path: str | None = None


def _install_python_packages(packages: Iterable[str]) -> bool:
    cmd = [sys.executable, "-m", "pip", "install", *packages]
    try:
        subprocess.check_call(cmd)
        return True
    except Exception:
        return False


def _download_and_extract_zip(url: str, dest: Path) -> str | None:
    # download to a temporary file and extract if it's a zip
    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
    except Exception:
        return None

    tmp = dest.with_suffix(".tmp")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "wb") as fh:
        for chunk in resp.iter_content(8192):
            fh.write(chunk)

    # try zip extraction
    try:
        import zipfile

        with zipfile.ZipFile(tmp, "r") as z:
            z.extractall(dest)
        tmp.unlink()
        # attempt to find mpv executable
        candidates = list(dest.rglob("mpv.exe"))
        if candidates:
            return str(candidates[0])
        # try non-windows name
        candidates = list(dest.rglob("mpv"))
        if candidates:
            return str(candidates[0])
    except Exception:
        try:
            tmp.unlink()
        except Exception:
            pass
    return None


def ensure_python_audio_deps() -> bool:
    packages = [
        "aubio>=0.4.9",
        "librosa>=0.10.2",
        "soundfile>=0.12.1",
    ]
    return _install_python_packages(packages)


def ensure_mpv_auto(mpv_url: str | None = None) -> tuple[bool, str | None]:
    """Attempt to download mpv from `mpv_url` (zip expected) and install to user .wizardcli.

    Returns (success, path_to_exe_or_none).
    """
    if mpv_url is None:
        # open the mpv download page for manual install
        webbrowser.open("https://mpv.io/installation/")
        return False, None

    target_dir = Path.home() / ".wizardcli" / "mpv"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = _download_and_extract_zip(mpv_url, target_dir)
    if path:
        # persist to user config
        cfg = {"mpv_exe": path}
        cfg_file = Path.home() / ".wizardcli" / "wizardcli.json"
        cfg_file.write_text(json.dumps(cfg), encoding="utf8")
        return True, path
    return False, None


def run_setup(auto_mpv: bool = False, mpv_url: str | None = None) -> SetupResult:
    py_ok = ensure_python_audio_deps()
    mpv_ok = False
    mpv_path = None
    if auto_mpv:
        ok, path = ensure_mpv_auto(mpv_url)
        mpv_ok = ok
        mpv_path = path

    return SetupResult(python_installed=py_ok, mpv_installed=mpv_ok, mpv_path=mpv_path)
