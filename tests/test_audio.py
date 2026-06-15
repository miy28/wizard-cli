from __future__ import annotations

from pathlib import Path

from wizardcli.audio import PlaybackController, _first_available_executable


class FakeProcess:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.terminated = False
        self.waited = False
        self._alive = True

    def poll(self):
        return None if self._alive else 0

    def wait(self, timeout: float | None = None):
        self.waited = True
        self._alive = False
        return 0

    def terminate(self) -> None:
        self.terminated = True
        self._alive = False


class FakeTransport:
    def __init__(self) -> None:
        self.sent: list[list[object]] = []
        self.closed = False

    def send(self, command):
        self.sent.append(list(command))
        return {"error": "success"}

    def close(self) -> None:
        self.closed = True


def test_preview_starts_mpv_and_loads_the_file(tmp_path: Path) -> None:
    process = FakeProcess()
    transport = FakeTransport()
    commands: list[list[str]] = []

    def process_factory(command: list[str]) -> FakeProcess:
        commands.append(command)
        return process

    controller = PlaybackController(
        mpv_executable="mpv",
        process_factory=process_factory,
        transport_factory=lambda _address: transport,
    )

    audio = tmp_path / "beat.mp3"
    audio.write_text("x", encoding="utf-8")

    controller.preview(audio)

    assert commands[0][0] == "mpv"
    assert any(item.startswith("--input-ipc-server=") for item in commands[0])
    assert transport.sent == [["loadfile", str(audio.resolve()), "replace"]]
    assert controller.current_path == audio.resolve()


def test_seek_sends_relative_command(tmp_path: Path) -> None:
    process = FakeProcess()
    transport = FakeTransport()

    controller = PlaybackController(
        mpv_executable="mpv",
        process_factory=lambda command: process,
        transport_factory=lambda _address: transport,
    )

    audio = tmp_path / "beat.mp3"
    audio.write_text("x", encoding="utf-8")

    controller.preview(audio)
    controller.seek(7.5)

    assert transport.sent[-1] == ["seek", 7.5, "relative"]


def test_preview_reuses_mpv_for_next_file(tmp_path: Path) -> None:
    process = FakeProcess()
    transport = FakeTransport()
    commands: list[list[str]] = []

    controller = PlaybackController(
        mpv_executable="mpv",
        process_factory=lambda command: commands.append(command) or process,
        transport_factory=lambda _address: transport,
    )

    first = tmp_path / "first.mp3"
    second = tmp_path / "second.mp3"
    first.write_text("x", encoding="utf-8")
    second.write_text("x", encoding="utf-8")

    controller.preview(first)
    controller.preview(second)

    assert len(commands) == 1
    assert transport.sent == [
        ["loadfile", str(first.resolve()), "replace"],
        ["loadfile", str(second.resolve()), "replace"],
    ]


def test_stop_closes_transport_and_terminates_process() -> None:
    process = FakeProcess()
    transport = FakeTransport()

    controller = PlaybackController(
        mpv_executable="mpv",
        process_factory=lambda command: process,
        transport_factory=lambda _address: transport,
    )

    controller._process = process
    controller._transport = transport
    controller.stop()

    assert transport.closed is True
    assert process.waited is True


def test_executable_resolver_skips_stale_configured_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    working_mpv = tmp_path / "mpv"
    working_mpv.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "wizardcli.audio.shutil.which",
        lambda value: str(working_mpv) if value == "mpv" else None,
    )

    resolved = _first_available_executable("C:\\missing\\mpv.exe", "mpv")

    assert resolved == str(working_mpv)
