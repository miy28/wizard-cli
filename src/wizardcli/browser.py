from __future__ import annotations

import os
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual import events
from textual import work
from textual.worker import get_current_worker
from textual.widgets import DirectoryTree


def _path_key(path: os.PathLike[str] | str) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


class MediaBrowser(DirectoryTree):
    show_root = False

    def __init__(self, root: Path, label: str, **kwargs) -> None:
        self.ICON_FILE = "♫ " if label == "songs" else "▧ "
        super().__init__(path=root, name=label, **kwargs)
        self.media_root = root
        self.border_title = label.capitalize()
        # sorting state
        self._sort_modes = [
            "default",
            "name_asc",
            "name_desc",
            "mtime_desc",
            "mtime_asc",
        ]
        self._sort_index = 0
        self.sort_mode = self._sort_modes[self._sort_index]
        self._committed_path_key: str | None = None

    def set_committed_path(self, path: Path | None) -> None:
        self._committed_path_key = _path_key(path) if path is not None else None
        self._clear_line_cache()
        self.refresh()

    def render_label(self, node, base_style: Style, style: Style) -> Text:
        label = super().render_label(node, base_style, style)
        data = getattr(node, "data", None)
        path = getattr(data, "path", None)
        if path is None or self._committed_path_key is None:
            return label

        if _path_key(path) == self._committed_path_key:
            label.stylize("bold green")
        return label

    def cycle_sort(self) -> str:
        """Cycle to the next sort mode and reload the tree.

        Returns the new sort mode string.
        """
        self._sort_index = (self._sort_index + 1) % len(self._sort_modes)
        self.sort_mode = self._sort_modes[self._sort_index]
        # trigger a reload of the tree contents
        try:
            # reload() returns an AwaitComplete; we can call it to schedule reload
            self.reload()
        except Exception:
            # best-effort, ignore reload errors here
            pass
        return self.sort_mode

    def set_sort_mode(self, mode: str) -> str:
        """Set the sort mode to one of the known modes and return the applied mode.

        If `mode` is not recognised, falls back to the default mode.
        """
        try:
            idx = self._sort_modes.index(mode)
        except ValueError:
            idx = 0
        self._sort_index = idx
        self.sort_mode = self._sort_modes[self._sort_index]
        try:
            # reload to apply ordering
            self.reload()
        except Exception:
            pass
        return self.sort_mode

    def jump_top(self) -> None:
        """Move cursor to the first line and scroll there."""
        try:
            self.cursor_line = 0
            self.scroll_to(0, 0, animate=False)
        except Exception:
            pass

    def jump_bottom(self) -> None:
        """Move cursor to the last visible line and scroll there."""
        try:
            # ensure tree lines are computed
            _ = self._tree_lines
            last = max(0, len(self._tree_lines) - 1)
            self.cursor_line = last
            self.scroll_to(0, self.cursor_line, animate=False)
        except Exception:
            pass

    def on_key(self, event: events.Key) -> None:
        """Keep left/right arrows from moving the tree cursor and delegate seeking to the app."""
        # normalize key string: textual may encode modifiers in the key name
        key = event.key or ""
        # handle shift modifier encoded as prefix like 'shift+left'
        is_shift = False
        if key.startswith("shift+"):
            is_shift = True
            key = key.split("+", 1)[1]

        # DirectoryTree may consume space, so handle pause directly here.
        if key in {"space", " "}:
            try:
                event.stop()
                self.app.action_toggle_pause()
            except Exception:
                pass
            return

        if key not in {"left", "right"}:
            return

        event.stop()
        app = self.app
        try:
            # support shift for larger seeks
            if key == "left":
                if is_shift or getattr(event, "shift", False):
                    app.action_seek_backward_large()
                else:
                    app.action_seek_backward()
            else:
                if is_shift or getattr(event, "shift", False):
                    app.action_seek_forward_large()
                else:
                    app.action_seek_forward()
        except Exception:
            pass

    @work(thread=True, exit_on_error=False)
    def _load_directory(self, node) -> list[Path]:
        """Load the directory contents honoring the selected sort mode."""
        assert node.data is not None
        path = node.data.path
        path = path.expanduser().resolve()

        # collect entries
        entries = list(self.filter_paths(self._directory_content(path, get_current_worker())))

        # choose key and order
        def name_key(path: Path) -> tuple[bool, str]:
            return not self._safe_is_dir(path), path.name.lower()

        def modified_key(path: Path) -> tuple[bool, float | int]:
            modified = path.stat().st_mtime if path.exists() else 0
            return not self._safe_is_dir(path), modified

        reverse = False
        if self.sort_mode == "default":
            key = name_key
        elif self.sort_mode == "name_asc":
            key = name_key
            reverse = False
        elif self.sort_mode == "name_desc":
            key = name_key
            reverse = True
        elif self.sort_mode == "mtime_desc":
            key = modified_key
            reverse = True
        elif self.sort_mode == "mtime_asc":
            key = modified_key
            reverse = False
        else:
            key = name_key

        try:
            return sorted(entries, key=key, reverse=reverse)
        except Exception:
            # fallback to default behaviour on any error
            return sorted(entries, key=name_key)
