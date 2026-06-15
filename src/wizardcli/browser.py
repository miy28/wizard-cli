from __future__ import annotations

from pathlib import Path
from typing import Iterable

from textual import events
from textual import work
from textual.worker import get_current_worker
from textual.widgets import DirectoryTree


class MediaBrowser(DirectoryTree):
    def __init__(self, root: Path, label: str, **kwargs) -> None:
        self.ICON_FILE = "♫ " if label == "songs" else "▧ "
        super().__init__(path=root, name=label, **kwargs)
        self.media_root = root
        self.border_title = label.capitalize()
        # hide the root node so the tree starts inside the given path
        try:
            self.show_root = False
        except Exception:
            pass
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
        reverse = False
        if self.sort_mode == "default":
            key = lambda p: (not self._safe_is_dir(p), p.name.lower())
        elif self.sort_mode == "name_asc":
            key = lambda p: (not self._safe_is_dir(p), p.name.lower())
            reverse = False
        elif self.sort_mode == "name_desc":
            key = lambda p: (not self._safe_is_dir(p), p.name.lower())
            reverse = True
        elif self.sort_mode == "mtime_desc":
            key = lambda p: (not self._safe_is_dir(p), p.stat().st_mtime if p.exists() else 0)
            reverse = True
        elif self.sort_mode == "mtime_asc":
            key = lambda p: (not self._safe_is_dir(p), p.stat().st_mtime if p.exists() else 0)
            reverse = False
        else:
            key = lambda p: (not self._safe_is_dir(p), p.name.lower())

        try:
            return sorted(entries, key=key, reverse=reverse)
        except Exception:
            # fallback to default behaviour on any error
            return sorted(entries, key=lambda path: (not self._safe_is_dir(path), path.name.lower()))
