from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text


class ChafaError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChafaPreview:
    path: Path
    width: int
    height: int
    art: Text


def find_chafa(executable: str = "chafa") -> str | None:
    candidate = Path(executable).expanduser()
    if candidate.is_file():
        return str(candidate)
    return shutil.which(executable)


def render_cover(
    path: Path,
    width: int,
    height: int,
    executable: str = "chafa",
    timeout: float = 20.0,
) -> ChafaPreview:
    chafa = find_chafa(executable)
    if chafa is None:
        raise ChafaError("chafa was not found on PATH")

    width = max(1, width)
    height = max(1, height)
    command = [
        chafa,
        "--format",
        "symbols",
        "--colors",
        "full",
        "--color-space",
        "din99d",
        "--work",
        "9",
        "--animate",
        "off",
        "--probe",
        "off",
        "--polite",
        "on",
        "--relative",
        "off",
        "--scale",
        "max",
        "--size",
        f"{width}x{height}",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ChafaError("chafa was not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ChafaError(f"chafa timed out rendering {path.name}") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() if exc.stderr else "unknown error"
        raise ChafaError(f"chafa failed for {path.name}: {detail}") from exc

    output = result.stdout.rstrip("\n")
    if not output:
        raise ChafaError(f"chafa produced no output for {path.name}")

    return ChafaPreview(
        path=path,
        width=width,
        height=height,
        art=Text.from_ansi(output),
    )
