from __future__ import annotations

from pathlib import Path

import pytest

from wizardcli import chafa


class FakeResult:
    stdout = "\x1b[38;2;255;0;0m##\x1b[0m\n"
    stderr = ""


def test_render_cover_builds_terminal_safe_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"image")
    calls = []

    monkeypatch.setattr(
        chafa,
        "find_chafa",
        lambda executable="chafa": "/opt/homebrew/bin/chafa",
    )

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return FakeResult()

    monkeypatch.setattr(chafa.subprocess, "run", fake_run)

    preview = chafa.render_cover(cover, 32, 14)

    command, kwargs = calls[0]
    assert command[:3] == ["/opt/homebrew/bin/chafa", "--format", "symbols"]
    assert command[command.index("--size") + 1] == "32x14"
    assert command[command.index("--animate") + 1] == "off"
    assert command[command.index("--color-space") + 1] == "din99d"
    assert command[command.index("--work") + 1] == "9"
    assert command[command.index("--relative") + 1] == "off"
    assert command[-1] == str(cover)
    assert kwargs["capture_output"] is True
    assert preview.art.plain == "##"


def test_render_cover_reports_missing_chafa(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(chafa, "find_chafa", lambda executable="chafa": None)

    with pytest.raises(chafa.ChafaError, match="not found"):
        chafa.render_cover(tmp_path / "cover.png", 20, 10)
