from __future__ import annotations

import socket
from getpass import getuser
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Label, Static
from rich.text import Text

from . import __version__
from .audio import PlaybackController, PlaybackError
from .browser import MediaBrowser
from .config import AppConfig, default_config
from .paths import AUDIO_EXTENSIONS
import json


def get_user_host_string() -> Text:
    try:
        username = getuser()
        hostname = socket.gethostname()
        # return Text.from_markup(f"{username}@{hostname}")
        return Text.from_markup("mikeyy")
    except Exception:
        return Text("unknown@unknown")


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
    ]

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or default_config()
        self.playback = PlaybackController()
        self._default_status_text = "Select a beat and cover to run the pipeline."
        self._committed_beat: Path | None = None
        self._committed_cover: Path | None = None
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

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Horizontal(id="panes"):
            yield MediaBrowser(self.config.songs_dir, "songs", id="songs-browser")
            yield MediaBrowser(self.config.covers_dir, "covers", id="covers-browser")
        # persistent sort indicator shown under the media browser panes
        yield Label("Sort: Default", id="sort-indicator")
        yield Static(self._default_status_text, id="status")
        yield Footer()

    def action_preview(self) -> None:
        if self._preview_path is None or self._preview_source_id != "songs-browser":
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
            if self._preview_path is not None and self._preview_source_id == "songs-browser":
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
            if self._preview_path is not None and self._preview_source_id == "songs-browser":
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
        # prefer the focused MediaBrowser, otherwise fall back to the first
        focused = None
        try:
            focused = self.focused if isinstance(self.focused, MediaBrowser) else None
        except Exception:
            focused = None

        try:
            if focused is None:
                focused = self.query_one(MediaBrowser)
        except Exception:
            pass

        if focused is None:
            return

        try:
            applied = focused.cycle_sort()
        except Exception:
            applied = getattr(focused, "sort_mode", "default")

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
        if self._preview_path is not None and self._preview_source_id == "songs-browser":
            return f"Previewing: {self._preview_path.name}"
        return self._default_status_text

    def _schedule_preview_settle(self) -> None:
        self._preview_debounce_generation += 1
        generation = self._preview_debounce_generation
        self.set_timer(self._preview_debounce_delay, lambda: self._settle_preview_debounce(generation))

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

    def action_jump_top(self) -> None:
        """Jump to top in the focused MediaBrowser, or the first one if none focused."""
        try:
            focused = self.focused
            if isinstance(focused, MediaBrowser):
                focused.jump_top()
                return
        except Exception:
            pass
        try:
            b = self.query_one(MediaBrowser)
            b.jump_top()
        except Exception:
            pass

    def action_jump_bottom(self) -> None:
        """Jump to bottom in the focused MediaBrowser, or the first one if none focused."""
        try:
            focused = self.focused
            if isinstance(focused, MediaBrowser):
                focused.jump_bottom()
                return
        except Exception:
            pass
        try:
            b = self.query_one(MediaBrowser)
            b.jump_bottom()
        except Exception:
            pass

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

        if source_id != "songs-browser":
            self._preview_path = None
            self._preview_source_id = None
            self._pending_preview = (None, None)
            self._preview_debounce_active = False
            self._preview_burst_has_moved = False
            self.playback.stop()
            return

        if path.suffix.lower() in AUDIO_EXTENSIONS and path.is_file():
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
            self._preview_path = None
            self._preview_source_id = None
            self._pending_preview = (None, None)
            self._preview_debounce_active = False
            self._preview_burst_has_moved = False
            self.playback.stop()

    def _commit_path(self, path: Path | None, source_id: str | None) -> None:
        """Commit the selected path for later encoding without triggering preview logic."""
        if path is None:
            return

        if source_id == "songs-browser":
            self._committed_beat = path
            self.set_activity(f"Committed beat: {path}")
        elif source_id == "covers-browser":
            self._committed_cover = path
            self.set_activity(f"Committed cover: {path}")

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
        if self._preview_path is None or self._preview_source_id != "songs-browser":
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

    def on_unmount(self) -> None:
        self.playback.stop()
