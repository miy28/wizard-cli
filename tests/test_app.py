from __future__ import annotations

from wizardcli.app import WizardApp
from wizardcli.config import default_config


class FakeStatus:
    def __init__(self) -> None:
        self.text = None

    def update(self, text: str) -> None:
        self.text = text


class FakePlayback:
    def __init__(self) -> None:
        self.seek_calls: list[float] = []
        self.preview_calls: list[str] = []
        self.stop_calls = 0

    def seek(self, seconds: float) -> None:
        self.seek_calls.append(seconds)

    def preview(self, path, restart: bool = False) -> None:
        self.preview_calls.append(path.name)

    def stop(self) -> None:
        self.stop_calls += 1


def test_seek_temp_activity_restores_preview_status(tmp_path) -> None:
    app = WizardApp(default_config(root_dir=tmp_path))
    status = FakeStatus()
    scheduled = {}
    playback = FakePlayback()

    app.query_one = lambda *args, **kwargs: status  # type: ignore[method-assign]
    app.set_timer = lambda delay, callback: scheduled.update(delay=delay, callback=callback)  # type: ignore[method-assign]
    app.playback = playback

    app._preview_path = tmp_path / "beat.mp3"
    app._preview_source_id = "songs-browser"

    app._seek_preview(5.0)

    assert playback.seek_calls == [5.0]
    assert status.text == "Seeked +5s: beat.mp3"
    assert scheduled["delay"] == 1.25

    scheduled["callback"]()
    assert status.text == "Previewing: beat.mp3"


def test_normal_activity_invalidates_pending_temp_restore(tmp_path) -> None:
    app = WizardApp(default_config(root_dir=tmp_path))
    status = FakeStatus()
    scheduled = {}
    playback = FakePlayback()

    app.query_one = lambda *args, **kwargs: status  # type: ignore[method-assign]
    app.set_timer = lambda delay, callback: scheduled.update(delay=delay, callback=callback)  # type: ignore[method-assign]
    app.playback = playback

    app._preview_path = tmp_path / "beat.mp3"
    app._preview_source_id = "songs-browser"

    app._seek_preview(5.0)
    app.set_activity("Committed beat: demo")
    scheduled["callback"]()

    assert status.text == "Committed beat: demo"


def test_preview_debounces_repeated_highlights(tmp_path) -> None:
    app = WizardApp(default_config(root_dir=tmp_path))
    status = FakeStatus()
    scheduled = {}
    playback = FakePlayback()

    app.query_one = lambda *args, **kwargs: status  # type: ignore[method-assign]
    app.set_timer = lambda delay, callback: scheduled.update(delay=delay, callback=callback)  # type: ignore[method-assign]
    app.playback = playback

    first = tmp_path / "one.mp3"
    second = tmp_path / "two.mp3"
    third = tmp_path / "three.mp3"
    first.write_text("x", encoding="utf-8")
    second.write_text("x", encoding="utf-8")
    third.write_text("x", encoding="utf-8")

    app._preview_soft_path(first, "songs-browser")
    app._preview_soft_path(second, "songs-browser")
    app._preview_soft_path(third, "songs-browser")

    assert playback.preview_calls == ["one.mp3", "two.mp3"]

    scheduled["callback"]()

    assert playback.preview_calls == ["one.mp3", "two.mp3", "three.mp3"]
    assert status.text == "Previewing: three.mp3"
