from __future__ import annotations

import os
import sys
import threading
import time
import weakref
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

MEDIA_EXTENSIONS = {
    ".aac",
    ".avi",
    ".flac",
    ".gif",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".m4v",
    ".m3u",
    ".m3u8",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".m4s",
    ".mpeg",
    ".mpg",
    ".ogg",
    ".png",
    ".ts",
    ".wav",
    ".webm",
    ".webp",
}
TEMPORARY_SUFFIXES = {".bak", ".cache", ".download", ".part", ".temp", ".tmp"}
DATABASE_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}
DATABASE_SUFFIXES = {".sqlite-shm", ".sqlite-wal"}
SETTINGS_NAMES = {
    ".env",
    ".env.local",
    "config.toml",
    "config.json",
    "preferences.json",
    "session.json",
    "settings.json",
    "settings.yaml",
    "settings.yml",
    "state.json",
}
MEDIA_CACHE_DIRECTORY_NAMES = {
    "media-cache",
    "mediacache",
    "media_cache",
}
THUMBNAIL_CACHE_DIRECTORY_NAMES = {
    "thumbnail-cache",
    "thumbnailcache",
    "thumbnail_cache",
    "thumbnails-cache",
}
IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".venv",
    "__pycache__",
    "dist",
    "fixtures",
    "node_modules",
    "playwright-artifacts",
    "site-packages",
}

_ACTIVE_MONITORS: weakref.WeakSet[FileSystemMonitor] = weakref.WeakSet()
_ACTIVE_MONITORS_LOCK = threading.Lock()
_AUDIT_HOOK_INSTALLED = False


@dataclass(frozen=True, order=True)
class Violation:
    path: str
    type: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def classify_path(path: str | Path, *, is_directory: bool = False) -> str | None:
    candidate = Path(path)
    name = candidate.name.casefold()

    if is_directory:
        if name in MEDIA_CACHE_DIRECTORY_NAMES:
            return "media_cache_directory"
        if name in THUMBNAIL_CACHE_DIRECTORY_NAMES:
            return "thumbnail_cache_directory"
        return None

    if name in SETTINGS_NAMES or (
        ("setting" in name or "preference" in name)
        and candidate.suffix.casefold() in {".json", ".yaml", ".yml", ".toml"}
    ):
        return "settings_file"
    if any(name.endswith(suffix) for suffix in DATABASE_SUFFIXES):
        return "database_file"

    suffix = candidate.suffix.casefold()
    while suffix in TEMPORARY_SUFFIXES or suffix[1:].isdigit():
        candidate = candidate.with_suffix("")
        suffix = candidate.suffix.casefold()
    if suffix in DATABASE_EXTENSIONS:
        return "database_file"
    if suffix in MEDIA_EXTENSIONS:
        return "media_file"
    if any(
        candidate.name.casefold().endswith(f"{extension}{temporary_suffix}")
        for extension in MEDIA_EXTENSIONS
        for temporary_suffix in TEMPORARY_SUFFIXES
    ):
        return "media_file"
    return None


class _WatchHandler(FileSystemEventHandler):
    def __init__(self, monitor: "FileSystemMonitor") -> None:
        self.monitor = monitor

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.event_type in {"opened", "closed_no_write"}:
            return
        self.monitor._record(event.src_path, is_directory=event.is_directory)
        if event.event_type == "moved":
            destination = getattr(event, "dest_path", None)
            if destination:
                self.monitor._record(destination, is_directory=event.is_directory)


class FileSystemMonitor:
    def __init__(
        self,
        roots: Iterable[str | Path],
        *,
        ignored_directories: Iterable[str] = IGNORED_DIRECTORY_NAMES,
    ) -> None:
        resolved_roots = {Path(root).expanduser().resolve() for root in roots}
        if not resolved_roots:
            raise ValueError("At least one filesystem monitoring root is required.")
        self.roots = tuple(sorted(resolved_roots, key=lambda path: str(path).casefold()))
        self.ignored_directories = {
            name.casefold() for name in ignored_directories
        }
        self._violations: set[Violation] = set()
        self._lock = threading.Lock()
        self._observer: Observer | None = None

    def __enter__(self) -> "FileSystemMonitor":
        self.start()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        if self._observer is not None:
            self.stop()

    @property
    def violations(self) -> tuple[Violation, ...]:
        with self._lock:
            return tuple(sorted(self._violations))

    def start(self) -> None:
        if self._observer is not None:
            raise RuntimeError("Filesystem monitoring has already started.")
        handler = _WatchHandler(self)
        observer = Observer()
        scheduled = 0
        for root in self.roots:
            if root.is_dir():
                observer.schedule(handler, str(root), recursive=True)
                scheduled += 1
        if scheduled == 0:
            raise FileNotFoundError("None of the monitoring roots are directories.")
        self._observer = observer
        global _AUDIT_HOOK_INSTALLED
        with _ACTIVE_MONITORS_LOCK:
            _ACTIVE_MONITORS.add(self)
            if not _AUDIT_HOOK_INSTALLED:
                sys.addaudithook(_dispatch_audit_event)
                _AUDIT_HOOK_INSTALLED = True
        observer.start()

    def stop(self) -> tuple[Violation, ...]:
        observer = self._observer
        if observer is None:
            raise RuntimeError("Filesystem monitoring has not started.")
        time.sleep(0.05)
        observer.event_queue.join()
        observer.stop()
        observer.join()
        with _ACTIVE_MONITORS_LOCK:
            _ACTIVE_MONITORS.discard(self)
        self._observer = None
        return self.violations

    def _is_in_scope(self, path: str | os.PathLike[str]) -> Path | None:
        try:
            candidate = Path(os.fsdecode(path)).expanduser()
            if not candidate.is_absolute():
                candidate = Path.cwd() / candidate
            candidate = candidate.resolve(strict=False)
        except (OSError, TypeError, ValueError):
            return None

        if any(
            part.casefold() in self.ignored_directories
            or part.casefold().startswith("playwright_chromiumdev_profile-")
            for part in candidate.parts
        ):
            return None
        if any(candidate == root or root in candidate.parents for root in self.roots):
            return candidate
        return None

    def _record(self, path: str | os.PathLike[str], *, is_directory: bool = False) -> None:
        candidate = self._is_in_scope(path)
        if candidate is None:
            return
        violation_type = classify_path(candidate, is_directory=is_directory)
        if violation_type is not None:
            violation = Violation(str(candidate), violation_type)
            with self._lock:
                self._violations.add(violation)

    def _audit_event(self, event: str, args: tuple[object, ...]) -> None:
        if event == "open" and args:
            path = args[0]
            mode = args[1] if len(args) > 1 else "r"
            flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
            writing_flags = (
                os.O_WRONLY
                | os.O_RDWR
                | os.O_CREAT
                | os.O_TRUNC
                | os.O_APPEND
            )
            if isinstance(mode, str) and any(flag in mode for flag in "wax+"):
                self._record(path)
            elif flags & writing_flags:
                self._record(path)
        elif event in {"os.remove", "os.unlink", "os.mkdir", "os.rmdir"} and args:
            self._record(args[0], is_directory=event in {"os.mkdir", "os.rmdir"})
        elif event in {"os.rename", "os.replace"} and len(args) >= 2:
            self._record(args[0])
            self._record(args[1])


def _dispatch_audit_event(event: str, args: tuple[object, ...]) -> None:
    with _ACTIVE_MONITORS_LOCK:
        monitors = tuple(_ACTIVE_MONITORS)
    for monitor in monitors:
        monitor._audit_event(event, args)


def default_monitor_roots(project_root: Path) -> tuple[Path, ...]:
    roots = {
        project_root.resolve(),
        Path(os.environ.get("TEMP", os.environ.get("TMP", Path.cwd()))).resolve(),
    }
    for variable in ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME"):
        value = os.environ.get(variable)
        if value:
            data_root = Path(value)
            if data_root.is_dir():
                roots.add(data_root.resolve())
    return tuple(sorted(roots, key=lambda path: str(path).casefold()))
