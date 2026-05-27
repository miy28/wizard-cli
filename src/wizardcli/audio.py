from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol


class PlaybackError(RuntimeError):
    pass


class _IpcConnection(Protocol):
    def send(self, command: Sequence[object]) -> dict[str, Any] | None:
        ...

    def close(self) -> None:
        ...


class _WindowsPipeConnection:
    def __init__(self, pipe_name: str) -> None:
        self._stream = open(pipe_name, "r+b", buffering=0)
        self._next_request_id = 1

    def send(self, command: Sequence[object]) -> dict[str, Any] | None:
        request_id = self._next_request_id
        self._next_request_id += 1
        payload = json.dumps({"command": list(command), "request_id": request_id}).encode("utf-8") + b"\n"
        self._stream.write(payload)
        self._stream.flush()
        while True:
            response = self._stream.readline()
            if not response:
                return None
            message = json.loads(response.decode("utf-8"))
            if message.get("request_id") == request_id:
                return message

    def close(self) -> None:
        try:
            self._stream.close()
        except Exception:
            pass


class _UnixSocketConnection:
    def __init__(self, socket_path: str) -> None:
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.connect(socket_path)
        self._stream = self._socket.makefile("rwb")
        self._next_request_id = 1

    def send(self, command: Sequence[object]) -> dict[str, Any] | None:
        request_id = self._next_request_id
        self._next_request_id += 1
        payload = json.dumps({"command": list(command), "request_id": request_id}).encode("utf-8") + b"\n"
        self._stream.write(payload)
        self._stream.flush()
        while True:
            response = self._stream.readline()
            if not response:
                return None
            message = json.loads(response.decode("utf-8"))
            if message.get("request_id") == request_id:
                return message

    def close(self) -> None:
        try:
            self._stream.close()
        except Exception:
            pass
        try:
            self._socket.close()
        except Exception:
            pass


class PlaybackController:
    def __init__(
        self,
        mpv_executable: str | None = None,
        seek_step_seconds: float = 5.0,
        process_factory: Callable[[list[str]], subprocess.Popen[bytes]] | None = None,
        transport_factory: Callable[[str], _IpcConnection] | None = None,
        ipc_timeout_seconds: float = 2.5,
        poll_interval_seconds: float = 0.05,
    ) -> None:
        # determine mpv executable in this order:
        # 1. explicit argument, 2. env WIZARDCLI_MPV_EXE, 3. user config file, 4. default 'mpv'
        env_path = os.environ.get("WIZARDCLI_MPV_EXE")

        # Look for a project-level config first (repo root or current working dir),
        # then fallback to the per-user config in the home directory.
        def _find_repo_root(start: Path) -> Path | None:
            for p in [start] + list(start.parents):
                if (p / "pyproject.toml").exists() or (p / ".git").exists():
                    return p
            return None

        project_root = _find_repo_root(Path.cwd())
        project_candidates: list[Path] = []
        if project_root is not None:
            project_candidates.append(project_root / ".wizardcli" / "wizardcli.json")
            project_candidates.append(project_root / ".wizardcli.json")
        else:
            project_candidates.append(Path.cwd() / ".wizardcli" / "wizardcli.json")
            project_candidates.append(Path.cwd() / ".wizardcli.json")

        config_path_value: str | None = None
        try:
            for cfg_path in project_candidates:
                if cfg_path.exists():
                    cfg = json.loads(cfg_path.read_text(encoding="utf8"))
                    config_path_value = cfg.get("mpv_exe")
                    break
            if config_path_value is None:
                user_cfg = Path.home() / ".wizardcli" / "wizardcli.json"
                if user_cfg.exists():
                    cfg = json.loads(user_cfg.read_text(encoding="utf8"))
                    config_path_value = cfg.get("mpv_exe")
        except Exception:
            config_path_value = None

        self._mpv_executable = (
            mpv_executable
            or env_path
            or config_path_value
            or "mpv"
        )
        self._seek_step_seconds = seek_step_seconds
        self._process_factory = process_factory or self._default_process_factory
        self._transport_factory = transport_factory or self._default_transport_factory
        self._ipc_timeout_seconds = ipc_timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._process: subprocess.Popen[bytes] | None = None
        self._transport: _IpcConnection | None = None
        self._current_path: Path | None = None
        self._ipc_address: str | None = None

    @property
    def current_path(self) -> Path | None:
        return self._current_path

    def preview(self, audio_path: Path, restart: bool = False) -> None:
        audio_path = audio_path.resolve()
        if self._current_path == audio_path and self._process and self._process.poll() is None:
            if not restart:
                return
            self.stop()

        self.stop()
        self._ipc_address = self._build_ipc_address()
        command = self._build_command(self._ipc_address)
        self._process = self._process_factory(command)
        self._transport = self._connect_transport(self._ipc_address)
        self._send(["loadfile", str(audio_path), "replace"])
        self._current_path = audio_path

    def seek(self, seconds: float | None = None) -> None:
        if self._current_path is None:
            raise PlaybackError("No active preview to seek")

        amount = self._seek_step_seconds if seconds is None else seconds
        self._send(["seek", amount, "relative"])

    def toggle_pause(self) -> bool:
        """Toggle pause/play on the current mpv instance and return the paused state.

        Read the current `pause` property and set it to the inverse to avoid
        race conditions with `cycle` followed immediately by `get_property`.
        """
        resp = self._send(["get_property", "pause"])
        current = bool(resp.get("data")) if resp and "data" in resp else False
        self._send(["set_property", "pause", (not current)])
        return not current

    def toggle_mute(self) -> bool:
        """Toggle mute on the current mpv instance and return the mute state.

        Read the current `mute` property then set it to the inverse so the
        returned value reflects the new state reliably.
        """
        resp = self._send(["get_property", "mute"])
        current = bool(resp.get("data")) if resp and "data" in resp else False
        self._send(["set_property", "mute", (not current)])
        return not current

    def set_mute(self, muted: bool) -> None:
        self._send(["set_property", "mute", bool(muted)])

    def stop(self) -> None:
        transport = self._transport
        self._transport = None

        process = self._process
        self._process = None
        self._current_path = None

        if transport is not None:
            try:
                transport.send(["quit"])
            except Exception:
                pass
            finally:
                transport.close()

        if process is None:
            return

        try:
            process.wait(timeout=0.5)
        except Exception:
            try:
                if process.poll() is None:
                    process.terminate()
            except Exception:
                pass

    def _send(self, command: Sequence[object]) -> dict[str, Any] | None:
        if self._transport is None:
            raise PlaybackError("mpv is not connected")

        response = self._transport.send(command)
        if response and response.get("error") not in (None, "success"):
            raise PlaybackError(str(response.get("error")))
        return response

    def _build_command(self, ipc_address: str) -> list[str]:
        executable = shutil.which(self._mpv_executable) or self._mpv_executable
        if not executable:
            raise PlaybackError("mpv executable not found")
        return [
            executable,
            "--idle=yes",
            "--force-window=no",
            "--no-terminal",
            "--no-video",
            "--hr-seek=no",
            "--audio-display=no",
            f"--input-ipc-server={ipc_address}",
        ]

    def _build_ipc_address(self) -> str:
        token = uuid.uuid4().hex
        if os.name == "nt":
            return rf"\\.\pipe\wizardcli-mpv-{token}"

        socket_path = Path(tempfile.gettempdir()) / f"wizardcli-mpv-{token}.sock"
        try:
            socket_path.unlink()
        except FileNotFoundError:
            pass
        return str(socket_path)

    def _connect_transport(self, ipc_address: str) -> _IpcConnection:
        deadline = time.monotonic() + self._ipc_timeout_seconds
        last_error: Exception | None = None

        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                raise PlaybackError("mpv exited before the IPC channel became ready")

            try:
                return self._transport_factory(ipc_address)
            except Exception as exc:
                last_error = exc
                time.sleep(self._poll_interval_seconds)

        message = f"Timed out waiting for mpv IPC at {ipc_address}"
        if last_error is not None:
            raise PlaybackError(message) from last_error
        raise PlaybackError(message)

    def _default_process_factory(self, command: list[str]) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _default_transport_factory(self, ipc_address: str) -> _IpcConnection:
        if os.name == "nt":
            return _WindowsPipeConnection(ipc_address)
        return _UnixSocketConnection(ipc_address)
