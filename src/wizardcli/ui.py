from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.scrollbar import ScrollTo
from textual.worker import get_current_worker
from textual.widgets import ContentSwitcher, Footer, Label, Static

from . import __version__
from .audio import PlaybackController, PlaybackError
from .browser import MediaBrowser
from .chafa import ChafaError, ChafaPreview, render_cover
from .config import AppConfig, default_config
from .paths import AUDIO_EXTENSIONS, COVER_EXTENSIONS


STAGES = {
    1: ("Song", "stage-song"),
    2: ("Cover", "stage-cover"),
    3: ("Description", "stage-description"),
    4: ("Review", "stage-review"),
}

POINTER_SCROLL_INTERVAL = 0.04
DETAIL_KEY_SCROLL_ROWS = 5


def _cover_preview_dimensions(
    container_width: int,
    container_height: int,
    detail: bool,
) -> tuple[int, int]:
    width = max(8, container_width - 4)
    if not detail:
        # Chafa preserves the source image's aspect ratio inside this bounding
        # box. In pick view, bound by both axes so the whole cover fits in the
        # right-side preview pane.
        height = max(4, container_height - 4)
        return width, height
    height = max(4, (width + 1) // 2)
    return width, height


class CoverPreviewScroll(VerticalScroll):
    BINDINGS = [
        *VerticalScroll.BINDINGS,
        Binding("ctrl+up", "cover_detail_scroll_top", "Top", show=False, priority=True),
        Binding("ctrl+down", "cover_detail_scroll_bottom", "Bottom", show=False, priority=True),
    ]

    def __init__(self, *children, **kwargs) -> None:
        super().__init__(*children, **kwargs)
        self.coalesce_pointer_scroll = False
        self.suppress_pointer_scroll = False
        self.fast_key_scroll = False
        self._pending_pointer_delta = 0.0
        self._pending_pointer_y: float | None = None
        self._pointer_scroll_scheduled = False

    def set_pointer_coalescing(
        self,
        enabled: bool,
        *,
        suppress: bool = False,
    ) -> None:
        self.coalesce_pointer_scroll = enabled
        self.suppress_pointer_scroll = suppress
        self.fast_key_scroll = enabled
        if not enabled:
            self._pending_pointer_delta = 0.0
            self._pending_pointer_y = None

    def _schedule_pointer_scroll(self) -> None:
        if self._pointer_scroll_scheduled:
            return
        self._pointer_scroll_scheduled = True
        self.set_timer(POINTER_SCROLL_INTERVAL, self._flush_pointer_scroll)

    def _queue_pointer_delta(self, delta: float) -> None:
        self._pending_pointer_delta += delta
        self._schedule_pointer_scroll()

    def _queue_pointer_position(self, y: float | None) -> None:
        if y is not None:
            self._pending_pointer_y = y
            self._pending_pointer_delta = 0.0
            self._schedule_pointer_scroll()

    def _flush_pointer_scroll(self) -> None:
        self._pointer_scroll_scheduled = False
        pending_y = self._pending_pointer_y
        pending_delta = self._pending_pointer_delta
        self._pending_pointer_y = None
        self._pending_pointer_delta = 0.0

        if pending_y is not None:
            self.scroll_to(y=pending_y, animate=False, immediate=True)
        elif pending_delta:
            self.scroll_relative(y=pending_delta, animate=False, immediate=True)

    def _on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        self.on_mouse_scroll_down(event)

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        if self.suppress_pointer_scroll:
            event.prevent_default()
            event.stop()
            return
        if not self.coalesce_pointer_scroll:
            super()._on_mouse_scroll_down(event)
            return
        self._queue_pointer_delta(self.app.scroll_sensitivity_y)
        event.stop()

    def _on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        self.on_mouse_scroll_up(event)

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        if self.suppress_pointer_scroll:
            event.prevent_default()
            event.stop()
            return
        if not self.coalesce_pointer_scroll:
            super()._on_mouse_scroll_up(event)
            return
        self._queue_pointer_delta(-self.app.scroll_sensitivity_y)
        event.stop()

    def _on_scroll_to(self, message: ScrollTo) -> None:
        self.on_scroll_to(message)

    def on_scroll_to(self, message: ScrollTo) -> None:
        if self.suppress_pointer_scroll:
            message.prevent_default()
            message.stop()
            return
        if not self.coalesce_pointer_scroll:
            super()._on_scroll_to(message)
            return
        self._queue_pointer_position(message.y)
        message.stop()

    def action_scroll_down(self) -> None:
        if not self.fast_key_scroll:
            super().action_scroll_down()
            return
        self.scroll_relative(y=DETAIL_KEY_SCROLL_ROWS, animate=False, immediate=True)

    def action_scroll_up(self) -> None:
        if not self.fast_key_scroll:
            super().action_scroll_up()
            return
        self.scroll_relative(y=-DETAIL_KEY_SCROLL_ROWS, animate=False, immediate=True)

    def action_cover_detail_scroll_bottom(self) -> None:
        if not self.fast_key_scroll:
            return
        self.scroll_end(animate=False, immediate=True)

    def action_cover_detail_scroll_top(self) -> None:
        if not self.fast_key_scroll:
            return
        self.scroll_home(animate=False, immediate=True)


def get_user_host_string() -> Text:
    return Text.from_markup("mikeyy")


class AppHeader(Horizontal):
    def compose(self) -> ComposeResult:
        yield Label(f"[b]wizard-cli[/] [dim]{__version__}[/]", id="app-title")
        yield Label(get_user_host_string(), id="app-user-host")


class WizardApp(App):
    CSS_PATH = Path(__file__).with_name("wizardcli.tcss")

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("p", "preview", "Preview"),
        ("space", "toggle_pause", "Play/Pause"),
        ("m", "toggle_mute", "Mute"),
        ("s", "cycle_sort", "Cycle Sort"),
        ("ctrl+up", "jump_top", "Jump Top"),
        ("ctrl+down", "jump_bottom", "Jump Bottom"),
        Binding("1", "stage_song", "Song", show=False, priority=True),
        Binding("2", "stage_cover", "Cover", show=False, priority=True),
        Binding("3", "stage_description", "Description", show=False, priority=True),
        Binding("4", "stage_review", "Review", show=False, priority=True),
        Binding("escape", "close_cover_detail", "Back", show=False, priority=True),
    ]

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__(ansi_color=True)
        self.config = config or default_config()
        self.playback = PlaybackController()
        self._default_status_text = "Select a beat and cover to run the pipeline."
        self._active_stage = 1
        self._committed_beat: Path | None = None
        self._committed_cover: Path | None = None
        self._highlighted_song: Path | None = None
        self._highlighted_cover: Path | None = None
        self._description_ready = False
        # UI state persistence
        self._ui_state_path = Path(self.config.root_dir) / ".wizardcli_state.json"
        self._ui_state: dict = self._load_ui_state()
        self._preview_path: Path | None = None
        self._preview_source_id: str | None = None
        self._activity_generation = 0
        self._preview_debounce_generation = 0
        self._preview_debounce_active = False
        self._preview_burst_has_moved = False
        self._pending_preview: tuple[Path | None, str | None] = (None, None)
        self._preview_debounce_delay = 0.2
        self._muted = False
        self._cover_preview_cache: dict[
            tuple[Path, int, int, int], ChafaPreview
        ] = {}
        self._cover_preview_generation = 0
        self._cover_detail = False

    def compose(self) -> ComposeResult:
        yield AppHeader()
        yield Label("", id="stage-indicator")
        with Horizontal(id="workspace"):
            with ContentSwitcher(initial="stage-song", id="stage-switcher"):
                yield MediaBrowser(self.config.songs_dir, "songs", id="stage-song")
                yield MediaBrowser(self.config.covers_dir, "covers", id="stage-cover")
                yield Static(
                    "Description controls will live here.\n\n"
                    "Artists\nDescriptors\nTitle\nBody\nGenerate / Regenerate",
                    id="stage-description",
                    classes="stage-placeholder",
                )
                yield Static(
                    "Review controls will live here.\n\n"
                    "Validate pipeline\nRender video\nApprove upload",
                    id="stage-review",
                    classes="stage-placeholder",
                )
            with CoverPreviewScroll(id="stage-preview"):
                yield Static("", id="stage-preview-art")
                yield Static("", id="stage-preview-content")
        yield Label("Sort: Default", id="sort-indicator")
        yield Static(self._default_status_text, id="status")
        yield Footer()

    def action_stage_song(self) -> None:
        self._select_stage(1)

    def action_stage_cover(self) -> None:
        self._select_stage(2)

    def action_stage_description(self) -> None:
        self._select_stage(3)

    def action_stage_review(self) -> None:
        self._select_stage(4)

    def action_close_cover_detail(self) -> None:
        if self._cover_detail:
            self._set_cover_detail(False)

    def _select_stage(self, stage: int) -> None:
        if stage not in STAGES:
            return
        if stage != 2 and self._cover_detail:
            self._set_cover_detail(False, rerender=False)
        self._active_stage = stage
        _, panel_id = STAGES[stage]
        try:
            self.query_one("#stage-switcher", ContentSwitcher).current = panel_id
            panel = self.query_one(f"#{panel_id}")
            if isinstance(panel, MediaBrowser):
                panel.focus()
        except Exception:
            pass
        self._refresh_stage_view()
        if stage == 2:
            path = self._highlighted_cover or self._committed_cover
            if path is not None:
                self._request_cover_preview(path)

    def _refresh_stage_view(self) -> None:
        try:
            indicator = Text()
            for number, (name, _) in STAGES.items():
                style = "bold #ff358d" if number == self._active_stage else "dim"
                indicator.append(f"{number} {name}", style=style)
                if number != len(STAGES):
                    indicator.append("   ")
            self.query_one("#stage-indicator", Label).update(indicator)
            preview_text: Text | str
            if self._active_stage == 2 and not self._cover_detail:
                preview_text = ""
            else:
                preview_text = self._stage_preview()
            self.query_one("#stage-preview-content", Static).update(preview_text)
            art = self.query_one("#stage-preview-art", Static)
            art.display = self._active_stage == 2
            if self._active_stage != 2:
                art.update("")
            preview = self.query_one("#stage-preview", CoverPreviewScroll)
            preview.set_pointer_coalescing(
                self._cover_detail,
                suppress=self._active_stage == 2 and not self._cover_detail,
            )
        except Exception:
            pass

    def _stage_preview(self) -> Text:
        if self._active_stage == 1:
            path = self._highlighted_song or self._committed_beat
            return self._media_preview(
                "♫  SONG PREVIEW",
                path,
                committed=path is not None and path == self._committed_beat,
            )
        if self._active_stage == 2:
            path = self._highlighted_cover or self._committed_cover
            return self._media_preview(
                "▧  COVER PREVIEW",
                path,
                committed=path is not None and path == self._committed_cover,
            )
        if self._active_stage == 3:
            text = Text("DESCRIPTION PREVIEW\n\n", style="bold #ff358d")
            text.append("No description generated yet.\n\n", style="dim")
            text.append("Stage 3 will collect artists, descriptors, title, and body.")
            return text

        text = Text("PIPELINE STATE\n\n", style="bold #ff358d")
        text.append(self._readiness_line("Song", self._committed_beat))
        text.append(self._readiness_line("Cover", self._committed_cover))
        text.append(self._readiness_line("Description", self._description_ready))
        text.append("\n")
        if self._committed_beat and self._committed_cover and self._description_ready:
            text.append("Ready to render.", style="bold green")
        else:
            text.append("Complete the missing stages before rendering.", style="dim")
        return text

    def _media_preview(
        self,
        icon: str,
        # heading: str,
        path: Path | None,
        committed: bool,
    ) -> Text:
        text = Text(f"{icon}\n\n", style="bold #ff358d")
        # text.append(f"{heading}\n\n", style="bold")
        if path is None:
            text.append("Highlight a file to preview it.", style="dim")
            return text

        try:
            stat = path.stat()
            size = _format_file_size(stat.st_size)
            modified_at = datetime.fromtimestamp(stat.st_mtime)
            time_text = modified_at.strftime("%I:%M %p").lstrip("0")
            modified = (
                f"{modified_at.strftime('%b')} {modified_at.day}, "
                f"{modified_at.year} at {time_text}"
            )
        except OSError:
            size = "Unavailable"
            modified = "Unavailable"

        text.append(f"{path.name}\n", style="bold")
        text.append(
            "Committed\n" if committed else "Highlighted\n",
            style="green" if committed else "dim",
        )
        text.append(f"\nKind: {path.suffix.lstrip('.').upper() or 'File'}\n")
        text.append(f"Size: {size}\n")
        text.append(f"Modified: {modified}\n")
        text.append(f"Where: {path.parent}")
        return text

    @staticmethod
    def _readiness_line(label: str, value: object) -> Text:
        ready = bool(value)
        return Text(
            f"{'✓' if ready else '·'} {label}: {'Ready' if ready else 'Missing'}\n",
            style="green" if ready else "dim",
        )

    def action_preview(self) -> None:
        if self._preview_path is None or self._preview_source_id != "stage-song":
            self.set_activity("Highlight a beat to preview it.")
            return

        try:
            self.playback.preview(self._preview_path, restart=True)
            self.set_activity(f"Previewing: {self._preview_path.name}")
        except PlaybackError as exc:
            self.set_activity(str(exc))

    def action_seek_backward(self) -> None:
        self._seek_preview(-5.0)

    def action_seek_forward(self) -> None:
        self._seek_preview(5.0)

    def action_seek_backward_large(self) -> None:
        self._seek_preview(-10.0)

    def action_seek_forward_large(self) -> None:
        self._seek_preview(10.0)

    def action_toggle_pause(self) -> None:
        try:
            paused = self.playback.toggle_pause()
            if self._preview_path is not None and self._preview_source_id == "stage-song":
                name = self._preview_path.name
                state = "Paused" if paused else "Playing"
                self.set_temp_activity(f"{state}: {name}", self._preview_activity_text())
            else:
                state = "Paused" if paused else "Playing"
                self.set_activity(state)
        except PlaybackError as exc:
            self.set_activity(str(exc))

    def action_toggle_mute(self) -> None:
        try:
            muted = self.playback.toggle_mute()
            self._muted = muted
            if self._preview_path is not None and self._preview_source_id == "stage-song":
                name = self._preview_path.name
                state = "Muted" if muted else "Unmuted"
                self.set_temp_activity(f"{state}: {name}", self._preview_activity_text())
            else:
                state = "Muted" if muted else "Unmuted"
                self.set_activity(state)
        except PlaybackError as exc:
            self.set_activity(str(exc))

    def action_cycle_sort(self) -> None:
        """Cycle sorting mode on the focused MediaBrowser and show message."""
        browser = self._active_browser()
        if browser is None:
            self.set_activity("Sorting is available in stages 1 and 2.")
            return

        try:
            applied = browser.cycle_sort()
        except Exception:
            applied = getattr(browser, "sort_mode", "default")

        # restore original verbose labels
        pretty = {
            "default": "Default sort",
            "name_asc": "Name A → Z",
            "name_desc": "Name Z → A",
            "mtime_desc": "Last edited New → Old",
            "mtime_asc": "Last edited Old → New",
        }.get(applied, applied)

        # update persistent activity status and small label using the actual applied mode
        self.set_activity(f"Updated sorting: {pretty}")
        try:
            self.query_one("#sort-indicator", Label).update(f"Sort: {pretty}")
        except Exception:
            pass

        # persist the selected sort mode
        try:
            self._ui_state["sort_mode"] = applied
            self._save_ui_state()
        except Exception:
            pass

    def _load_ui_state(self) -> dict:
        try:
            if self._ui_state_path.exists():
                return json.loads(self._ui_state_path.read_text(encoding="utf8"))
        except Exception:
            pass
        return {}

    def _save_ui_state(self) -> None:
        try:
            self._ui_state_path.parent.mkdir(parents=True, exist_ok=True)
            self._ui_state_path.write_text(json.dumps(self._ui_state), encoding="utf8")
        except Exception:
            pass

    def _update_activity(self, text: str) -> None:
        try:
            self.query_one("#status", Static).update(text)
        except Exception:
            pass

    def _restore_temp_activity(self, generation: int, text: str) -> None:
        if generation != self._activity_generation:
            return
        self._update_activity(text)

    def _preview_activity_text(self) -> str:
        if self._preview_path is not None and self._preview_source_id == "stage-song":
            return f"Previewing: {self._preview_path.name}"
        return self._default_status_text

    def _schedule_preview_settle(self) -> None:
        self._preview_debounce_generation += 1
        generation = self._preview_debounce_generation
        self.set_timer(
            self._preview_debounce_delay,
            lambda: self._settle_preview_debounce(generation),
        )

    def _settle_preview_debounce(self, generation: int) -> None:
        if generation != self._preview_debounce_generation:
            return

        path, source_id = self._pending_preview
        self._pending_preview = (None, None)
        if path is not None and source_id is not None and path != self._preview_path:
            self._play_preview(path, source_id)
            return

        self._preview_debounce_active = False
        self._preview_burst_has_moved = False

    def _play_preview(self, path: Path, source_id: str) -> None:
        try:
            self.playback.preview(path)
            if self._muted:
                self.playback.set_mute(True)
            self._preview_path = path
            self._preview_source_id = source_id
            self._preview_debounce_active = True
            self._preview_burst_has_moved = False
            self._pending_preview = (None, None)
            self.set_activity(f"Previewing: {path.name}")
            self._schedule_preview_settle()
        except Exception:
            self.set_activity("mpv preview failed.")

    def on_mount(self) -> None:
        """Apply persisted UI state when app mounts."""
        # apply saved sort mode to browsers
        mode = self._ui_state.get("sort_mode")
        if mode:
            for b in self.query(MediaBrowser):
                try:
                    applied = b.set_sort_mode(mode)
                    # update indicator using the actual applied mode
                    pretty = {
                        "default": "Default sort",
                        "name_asc": "Name A → Z",
                        "name_desc": "Name Z → A",
                        "mtime_desc": "Last edited New → Old",
                        "mtime_asc": "Last edited Old → New",
                    }.get(applied, applied)
                    try:
                        self.query_one("#sort-indicator", Label).update(f"Sort: {pretty}")
                        self.set_activity(f"Sorting restored: {pretty}")
                    except Exception:
                        pass
                except Exception:
                    pass
        self._refresh_stage_view()

    def action_jump_top(self) -> None:
        """Jump to top in the focused MediaBrowser, or the first one if none focused."""
        if self._cover_detail:
            try:
                self.query_one("#stage-preview", CoverPreviewScroll).action_cover_detail_scroll_top()
            except Exception:
                pass
            return
        browser = self._active_browser()
        if browser is not None:
            browser.jump_top()

    def action_jump_bottom(self) -> None:
        """Jump to bottom in the focused MediaBrowser, or the first one if none focused."""
        if self._cover_detail:
            try:
                self.query_one("#stage-preview", CoverPreviewScroll).action_cover_detail_scroll_bottom()
            except Exception:
                pass
            return
        browser = self._active_browser()
        if browser is not None:
            browser.jump_bottom()

    def _active_browser(self) -> MediaBrowser | None:
        if self._active_stage not in (1, 2):
            return None
        _, panel_id = STAGES[self._active_stage]
        try:
            return self.query_one(f"#{panel_id}", MediaBrowser)
        except Exception:
            return None

    def set_activity(self, text: str) -> None:
        """Set the main activity/status line (`#status`) to `text`."""
        self._activity_generation += 1
        self._update_activity(text)

    def set_temp_activity(self, text: str, restore_text: str, delay: float = 1.25) -> None:
        """Show a temporary activity message and restore it after `delay` seconds."""
        self._activity_generation += 1
        generation = self._activity_generation
        self._update_activity(text)
        self.set_timer(delay, lambda: self._restore_temp_activity(generation, restore_text))

    def _preview_soft_path(self, path: Path | None, source_id: str | None) -> None:
        """Preview the soft-selected path immediately without committing state."""
        if path is None:
            return

        if source_id == "stage-cover":
            self._highlighted_cover = (
                path
                if path.is_file() and path.suffix.lower() in COVER_EXTENSIONS
                else None
            )
            self._refresh_stage_view()
            if self._highlighted_cover is not None:
                self._request_cover_preview(self._highlighted_cover)
            return

        if source_id == "stage-song" and path.suffix.lower() in AUDIO_EXTENSIONS and path.is_file():
            self._highlighted_song = path
            self._refresh_stage_view()
            if self._preview_path is None or self._preview_source_id != source_id:
                self._play_preview(path, source_id)
                return

            if path == self._preview_path:
                return

            if self._preview_debounce_active and not self._preview_burst_has_moved:
                self._play_preview(path, source_id)
                self._preview_burst_has_moved = True
                return

            self._pending_preview = (path, source_id)
            self._schedule_preview_settle()
        else:
            self._highlighted_song = None
            self._preview_path = None
            self._preview_source_id = None
            self._pending_preview = (None, None)
            self._preview_debounce_active = False
            self._preview_burst_has_moved = False
            self.playback.stop()
            self._refresh_stage_view()

    def _commit_path(self, path: Path | None, source_id: str | None) -> None:
        """Commit the selected path for later encoding without triggering preview logic."""
        if path is None:
            return

        if source_id == "stage-song":
            self._committed_beat = path
            try:
                self.query_one("#stage-song", MediaBrowser).set_committed_path(path)
            except Exception:
                pass
            self.set_activity(f"Committed beat: {path}")
        elif source_id == "stage-cover":
            self._committed_cover = path
            try:
                self.query_one("#stage-cover", MediaBrowser).set_committed_path(path)
            except Exception:
                pass
            self.set_activity(f"Committed cover: {path}")
        self._refresh_stage_view()
        if source_id == "stage-cover":
            self._set_cover_detail(True)

    def _set_cover_detail(self, enabled: bool, rerender: bool = True) -> None:
        self._cover_detail = enabled
        try:
            workspace = self.query_one("#workspace", Horizontal)
            if enabled:
                workspace.add_class("cover-detail")
                preview = self.query_one("#stage-preview", CoverPreviewScroll)
                preview.set_pointer_coalescing(True)
                preview.focus()
                self.query_one("#stage-preview-content", Static).update(self._stage_preview())
                self.set_activity("Cover committed. Press Esc to return to the browser.")
            else:
                preview = self.query_one("#stage-preview", CoverPreviewScroll)
                preview.set_pointer_coalescing(False, suppress=True)
                try:
                    self.query_one("#stage-preview-art", Static).update("")
                    self.query_one("#stage-preview-content", Static).update("")
                    preview.scroll_to(y=0, animate=False, immediate=True)
                except Exception:
                    pass
                workspace.remove_class("cover-detail")
                if self._active_stage == 2:
                    self.query_one("#stage-cover", MediaBrowser).focus()
        except Exception:
            return

        if rerender:
            path = self._committed_cover or self._highlighted_cover
            if path is not None:
                self.call_after_refresh(self._request_cover_preview, path)

    def _event_path(self, event) -> tuple[Path | None, str | None]:
        node = getattr(event, "node", None)
        data = getattr(node, "data", None)
        path = getattr(data, "path", None)
        control = getattr(event, "control", None)
        source_id = getattr(control, "id", None)
        return path, source_id

    def on_tree_node_highlighted(self, event) -> None:
        """Preview the soft-selected item immediately without committing it."""
        try:
            path, source_id = self._event_path(event)
            self._preview_soft_path(path, source_id)
        except Exception:
            pass

    def on_directory_tree_file_selected(self, event) -> None:
        """Commit the selected file on Enter/click and keep preview separate."""
        try:
            path, source_id = self._event_path(event)
            self._commit_path(path, source_id)
        except Exception:
            pass

    def on_directory_tree_directory_selected(self, event) -> None:
        """Ignore folder commits for now; commit is reserved for file paths."""
        return

    def _seek_preview(self, seconds: float) -> None:
        if self._preview_path is None or self._preview_source_id != "stage-song":
            self.set_activity("No active beat preview to seek.")
            return

        try:
            self.playback.seek(seconds)
            direction = "+" if seconds >= 0 else ""
            self.set_temp_activity(
                f"Seeked {direction}{seconds:g}s: {self._preview_path.name}",
                self._preview_activity_text(),
            )
        except PlaybackError as exc:
            self.set_activity(str(exc))

    def _request_cover_preview(self, path: Path) -> None:
        if not path.is_file() or path.suffix.lower() not in COVER_EXTENSIONS:
            return

        try:
            container = self.query_one("#stage-preview", CoverPreviewScroll)
            width, height = _cover_preview_dimensions(
                container.size.width,
                container.size.height,
                self._cover_detail,
            )
            modified = path.stat().st_mtime_ns
            art = self.query_one("#stage-preview-art", Static)
        except Exception:
            return

        self._cover_preview_generation += 1
        generation = self._cover_preview_generation
        cache_key = (path, width, height, modified)
        cached = self._cover_preview_cache.get(cache_key)
        if cached is not None:
            art.update(cached.art)
            return

        art.update(Text("Rendering cover preview...", style="dim"))
        self._render_cover_preview(path, width, height, modified, generation)

    @work(thread=True, exclusive=True, group="cover-preview", exit_on_error=False)
    def _render_cover_preview(
        self,
        path: Path,
        width: int,
        height: int,
        modified: int,
        generation: int,
    ) -> None:
        worker = get_current_worker()
        try:
            preview = render_cover(path, width, height)
        except Exception as exc:
            if not worker.is_cancelled:
                message = str(exc) if isinstance(exc, ChafaError) else f"Cover preview failed: {exc}"
                self.call_from_thread(
                    self._apply_cover_preview_error,
                    path,
                    generation,
                    message,
                )
            return

        if worker.is_cancelled:
            return
        self.call_from_thread(
            self._apply_cover_preview,
            preview,
            modified,
            generation,
        )

    def _apply_cover_preview(
        self,
        preview: ChafaPreview,
        modified: int,
        generation: int,
    ) -> None:
        cache_key = (preview.path, preview.width, preview.height, modified)
        self._cover_preview_cache[cache_key] = preview
        current = self._highlighted_cover or self._committed_cover
        if generation != self._cover_preview_generation or current != preview.path:
            return
        if self._active_stage == 2:
            self.query_one("#stage-preview-art", Static).update(preview.art)

    def _apply_cover_preview_error(
        self,
        path: Path,
        generation: int,
        message: str,
    ) -> None:
        current = self._highlighted_cover or self._committed_cover
        if generation != self._cover_preview_generation or current != path:
            return
        if self._active_stage == 2:
            text = Text("▧\n\n", style="bold #ff358d")
            text.append(message, style="dim")
            self.query_one("#stage-preview-art", Static).update(text)

    def on_unmount(self) -> None:
        self.playback.stop()


def _format_file_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"
