from __future__ import annotations

from types import SimpleNamespace

from rich.style import Style
from rich.text import Text

from wizardcli.models import DescriptionDraft, DescriptionInputs, AudioAnalysisResult, MetadataContext
from wizardcli.ui import (
    CoverPreviewScroll,
    DescriptionForm,
    WizardApp,
    _append_metadata_row,
    _cover_preview_dimensions,
    _split_csv,
)
from wizardcli.browser import MediaBrowser
from wizardcli.config import default_config
from wizardcli.theme import WIZARD_READY


class FakeStatus:
    def __init__(self) -> None:
        self.text = None

    def update(self, text: str) -> None:
        self.text = text


class FakeEvent:
    def __init__(self, key: str = "", character: str | None = None) -> None:
        self.key = key
        self.character = character
        self.stopped = False
        self.default_prevented = False

    def stop(self) -> None:
        self.stopped = True

    def prevent_default(self) -> None:
        self.default_prevented = True


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


class FakeWorkspace:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def add_class(self, name: str) -> None:
        self.calls.append(f"add:{name}")

    def remove_class(self, name: str) -> None:
        self.calls.append(f"remove:{name}")


class FakePreviewPane:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def set_pointer_coalescing(self, enabled: bool, *, suppress: bool = False) -> None:
        self.calls.append(f"coalesce:{enabled}:{suppress}")

    def focus(self) -> None:
        self.calls.append("preview-focus")

    def scroll_to(self, **kwargs) -> None:
        self.calls.append(f"scroll:{kwargs}")


class FakeArt:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def update(self, value: str) -> None:
        self.calls.append(f"art:{value}")


class FakeContent:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def update(self, value) -> None:
        self.calls.append(f"content:{value}")


class FakeBrowser:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def focus(self) -> None:
        self.calls.append("browser-focus")


def test_cover_detail_preview_uses_full_width_for_scrollable_large_view() -> None:
    width, height = _cover_preview_dimensions(240, 44, detail=True)

    assert width == 236
    assert height == 118


def test_regular_cover_preview_fits_inside_viewport() -> None:
    assert _cover_preview_dimensions(64, 44, detail=False) == (60, 40)


def test_cover_preview_coalesces_pointer_wheel_events(monkeypatch) -> None:
    preview = CoverPreviewScroll()
    callbacks = []
    scroll_calls = []
    monkeypatch.setattr(
        preview,
        "set_timer",
        lambda delay, callback: callbacks.append(callback),
    )
    monkeypatch.setattr(
        preview,
        "scroll_relative",
        lambda **kwargs: scroll_calls.append(kwargs),
    )

    preview._queue_pointer_delta(3)
    preview._queue_pointer_delta(3)

    assert len(callbacks) == 1
    callbacks[0]()
    assert scroll_calls == [{"y": 6.0, "animate": False, "immediate": True}]


def test_cover_preview_coalesces_scrollbar_drag_to_latest_position(monkeypatch) -> None:
    preview = CoverPreviewScroll()
    callbacks = []
    scroll_calls = []
    monkeypatch.setattr(
        preview,
        "set_timer",
        lambda delay, callback: callbacks.append(callback),
    )
    monkeypatch.setattr(
        preview,
        "scroll_to",
        lambda **kwargs: scroll_calls.append(kwargs),
    )

    preview._queue_pointer_position(12)
    preview._queue_pointer_position(37)

    assert len(callbacks) == 1
    callbacks[0]()
    assert scroll_calls == [{"y": 37, "animate": False, "immediate": True}]


def test_cover_detail_arrow_scroll_moves_five_rows(monkeypatch) -> None:
    preview = CoverPreviewScroll()
    scroll_calls = []
    monkeypatch.setattr(
        preview,
        "scroll_relative",
        lambda **kwargs: scroll_calls.append(kwargs),
    )

    preview.set_pointer_coalescing(True)
    preview.action_scroll_down()
    preview.action_scroll_up()

    assert scroll_calls == [
        {"y": 5, "animate": False, "immediate": True},
        {"y": -5, "animate": False, "immediate": True},
    ]


def test_cover_detail_ctrl_arrows_jump_to_top_and_bottom(monkeypatch) -> None:
    preview = CoverPreviewScroll()
    calls = []
    monkeypatch.setattr(
        preview,
        "scroll_end",
        lambda **kwargs: calls.append(("end", kwargs)),
    )
    monkeypatch.setattr(
        preview,
        "scroll_home",
        lambda **kwargs: calls.append(("home", kwargs)),
    )

    preview.set_pointer_coalescing(True)
    preview.action_cover_detail_scroll_bottom()
    preview.action_cover_detail_scroll_top()

    assert calls == [
        ("end", {"animate": False, "immediate": True}),
        ("home", {"animate": False, "immediate": True}),
    ]


def test_cover_detail_app_ctrl_jump_routes_to_preview_not_browser(tmp_path) -> None:
    app = WizardApp(default_config(root_dir=tmp_path))
    calls = []
    preview = FakePreviewPane(calls)
    browser = FakeBrowser(calls)
    browser.jump_top = lambda: calls.append("browser-top")  # type: ignore[method-assign]
    browser.jump_bottom = lambda: calls.append("browser-bottom")  # type: ignore[method-assign]
    preview.action_cover_detail_scroll_top = lambda: calls.append("preview-top")  # type: ignore[attr-defined]
    preview.action_cover_detail_scroll_bottom = lambda: calls.append("preview-bottom")  # type: ignore[attr-defined]

    def fake_query_one(selector, *args, **kwargs):
        return {
            "#stage-preview": preview,
            "#stage-cover": browser,
        }[selector]

    app.query_one = fake_query_one  # type: ignore[method-assign]
    app._cover_detail = True
    app._active_stage = 2

    app.action_jump_top()
    app.action_jump_bottom()

    assert calls == ["preview-top", "preview-bottom"]


def test_cover_preview_coalesces_pointer_scroll_in_detail_mode() -> None:
    preview = CoverPreviewScroll()
    callbacks = []
    scroll_calls = []
    preview.set_timer = lambda delay, callback: callbacks.append(callback)  # type: ignore[method-assign]
    preview.scroll_relative = lambda **kwargs: scroll_calls.append(kwargs)  # type: ignore[method-assign]

    preview.set_pointer_coalescing(True)
    preview._queue_pointer_delta(3)

    assert preview.coalesce_pointer_scroll is True
    assert preview.suppress_pointer_scroll is False
    callbacks[0]()
    assert scroll_calls == [{"y": 3.0, "animate": False, "immediate": True}]


def test_cover_pick_mode_suppresses_pointer_scroll() -> None:
    preview = CoverPreviewScroll()
    event = FakeEvent()

    preview.set_pointer_coalescing(False, suppress=True)
    preview._on_mouse_scroll_down(event)

    assert event.stopped is True
    assert event.default_prevented is True


def test_exiting_cover_detail_clears_large_art_before_layout_shrinks(tmp_path) -> None:
    app = WizardApp(default_config(root_dir=tmp_path))
    calls = []
    cover = tmp_path / "cover.png"
    cover.write_text("x", encoding="utf-8")
    app._committed_cover = cover
    app._cover_detail = True
    app._active_stage = 2

    workspace = FakeWorkspace(calls)
    preview = FakePreviewPane(calls)
    art = FakeArt(calls)
    content = FakeContent(calls)
    browser = FakeBrowser(calls)

    def fake_query_one(selector, *args, **kwargs):
        return {
            "#workspace": workspace,
            "#stage-preview": preview,
            "#stage-preview-art": art,
            "#stage-preview-content": content,
            "#stage-cover": browser,
        }[selector]

    app.query_one = fake_query_one  # type: ignore[method-assign]
    app.call_after_refresh = lambda callback, path: calls.append(f"rerender:{path.name}")  # type: ignore[method-assign]

    app._set_cover_detail(False)

    assert calls.index("art:") < calls.index("remove:cover-detail")
    assert calls.index("content:") < calls.index("remove:cover-detail")
    assert "rerender:cover.png" in calls


def test_media_browsers_use_terminal_safe_file_icons(tmp_path) -> None:
    songs = MediaBrowser(tmp_path, "songs")
    covers = MediaBrowser(tmp_path, "covers")

    assert songs.ICON_FILE == "♫ "
    assert covers.ICON_FILE == "▧ "


def test_media_browsers_hide_library_root(tmp_path) -> None:
    songs = MediaBrowser(tmp_path / "cooks", "songs")
    covers = MediaBrowser(tmp_path / "covers", "covers")

    assert songs.show_root is False
    assert covers.show_root is False


def test_media_browser_renders_committed_file_green(tmp_path) -> None:
    browser = MediaBrowser(tmp_path, "songs")
    beat = tmp_path / "beat.mp3"
    beat.write_text("x", encoding="utf-8")
    node = browser.root.add_leaf("beat.mp3", data=SimpleNamespace(path=beat))

    browser.set_committed_path(beat)
    label = browser.render_label(node, Style(), Style())

    assert any(WIZARD_READY in str(span.style) for span in label.spans)


def test_seek_temp_activity_restores_preview_status(tmp_path) -> None:
    app = WizardApp(default_config(root_dir=tmp_path))
    status = FakeStatus()
    scheduled = {}
    playback = FakePlayback()

    app.query_one = lambda *args, **kwargs: status  # type: ignore[method-assign]
    app.set_timer = lambda delay, callback: scheduled.update(delay=delay, callback=callback)  # type: ignore[method-assign]
    app.playback = playback

    app._preview_path = tmp_path / "beat.mp3"
    app._preview_source_id = "stage-song"

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
    app._preview_source_id = "stage-song"

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

    app._preview_soft_path(first, "stage-song")
    app._preview_soft_path(second, "stage-song")
    app._preview_soft_path(third, "stage-song")

    assert playback.preview_calls == ["one.mp3", "two.mp3"]

    scheduled["callback"]()

    assert playback.preview_calls == ["one.mp3", "two.mp3", "three.mp3"]
    assert status.text == "Previewing: three.mp3"


def test_stage_switching_preserves_committed_media(tmp_path) -> None:
    app = WizardApp(default_config(root_dir=tmp_path))
    beat = tmp_path / "beat.mp3"
    cover = tmp_path / "cover.png"

    app._commit_path(beat, "stage-song")
    app._commit_path(cover, "stage-cover")
    app._select_stage(4)

    assert app._active_stage == 4
    assert app._committed_beat == beat
    assert app._committed_cover == cover


def test_review_preview_reports_missing_description(tmp_path) -> None:
    app = WizardApp(default_config(root_dir=tmp_path))
    app._active_stage = 4
    app._committed_beat = tmp_path / "beat.mp3"
    app._committed_cover = tmp_path / "cover.png"

    preview = app._stage_preview().plain

    assert "Song: Ready" in preview
    assert "Cover: Ready" in preview
    assert "Description: Missing" in preview


def test_file_metadata_row_dims_value_only() -> None:
    text = Text()

    _append_metadata_row(text, "Kind", "MP3", newline=False)

    assert text.plain == "Kind MP3"
    assert any(
        span.start == len("Kind ")
        and span.end == len("Kind MP3")
        and "dim" in str(span.style)
        for span in text.spans
    )


def test_split_csv_cleans_and_dedupes_terms() -> None:
    assert _split_csv(" Carti, uzi, Carti ,, beat switch ") == [
        "Carti",
        "uzi",
        "beat switch",
    ]


def test_description_form_commits_textual_input_value() -> None:
    form = DescriptionForm()

    form.on_key(FakeEvent("enter"))
    form.edit_input = SimpleNamespace(value="Carti", remove=lambda: None)
    form._commit_edit()

    form.on_key(FakeEvent("down"))
    form.on_key(FakeEvent("enter"))
    form.edit_input = SimpleNamespace(value="rage", remove=lambda: None)
    form._commit_edit()

    inputs = form.description_inputs()

    assert inputs.artist_names == ["Carti"]
    assert inputs.descriptors == ["rage"]


def test_description_form_hides_plain_text_value_while_input_is_mounted() -> None:
    form = DescriptionForm()

    form.on_key(FakeEvent("enter"))
    rendered = form._render_form().plain.splitlines()[0]

    assert rendered == "> Artists: "


def test_description_form_empty_edit_input_has_no_placeholder(monkeypatch) -> None:
    form = DescriptionForm()
    mounted = []

    form.mount = lambda widget: mounted.append(widget)  # type: ignore[method-assign]
    monkeypatch.setattr("wizardcli.ui.Input.focus", lambda self: None)
    form._mount_edit_input("artists")

    assert form.edit_input is mounted[0]
    assert form.edit_input.placeholder == ""


def test_description_form_cancel_keeps_existing_value() -> None:
    form = DescriptionForm()
    form.values["artists"] = "Carti"

    form.on_key(FakeEvent("enter"))
    form.edit_input = SimpleNamespace(value="12", remove=lambda: None)
    form.on_key(FakeEvent("escape"))

    assert form.values["artists"] == "Carti"


def test_description_draft_marks_review_ready(tmp_path) -> None:
    app = WizardApp(default_config(root_dir=tmp_path))
    app._active_stage = 4
    app._committed_beat = tmp_path / "beat.mp3"
    app._committed_cover = tmp_path / "cover.png"
    draft = DescriptionDraft(
        inputs=DescriptionInputs(["Carti"], ["rage"]),
        title="Carti type beat",
        body="body",
        analysis=AudioAnalysisResult(150.0, "D", 0.9),
        metadata=MetadataContext(
            keywords=["Carti type beat"],
            artists=["Carti"],
            descriptors=["rage"],
            summary="Carti type beat",
            bpm=150.0,
            key="D",
        ),
        description="Carti type beat\nbody",
    )

    app._apply_description_draft(draft, app._description_generation)
    preview = app._stage_preview().plain

    assert app._description_ready is True
    assert "Description: Ready" in preview


def test_lastfm_status_reports_missing_key(monkeypatch, tmp_path) -> None:
    app = WizardApp(default_config(root_dir=tmp_path))
    monkeypatch.setattr("wizardcli.ui.get_lastfm_api_key", lambda: None)

    assert app._lastfm_status_text() == "Last.fm: off (no API key configured)"


def test_lastfm_status_reports_used_modifier_counts(monkeypatch, tmp_path) -> None:
    app = WizardApp(default_config(root_dir=tmp_path))
    monkeypatch.setattr("wizardcli.ui.get_lastfm_api_key", lambda: "demo-key")
    app._description_draft = DescriptionDraft(
        inputs=DescriptionInputs(["Carti"], []),
        title="Carti type beat",
        body="body",
        analysis=None,
        metadata=MetadataContext(
            keywords=["Carti type beat"],
            artists=["Carti"],
            summary="Carti type beat",
            lastfm_enabled=True,
            lastfm_similar_artists=["Ken Carson", "Destroy Lonely"],
            lastfm_discovered_descriptors=["rage"],
        ),
        description="Carti type beat\nbody",
    )

    assert app._lastfm_status_text() == "Last.fm: used 2 similar artists and 1 discovered tags"
