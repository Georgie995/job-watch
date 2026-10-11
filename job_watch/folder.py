"""Progress signal 1: a watched folder growing (for example a restore destination).

Read-only: only names, sizes and modification times are looked at. Nothing is opened or changed.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FolderSnapshot:
    total_bytes: int
    file_count: int
    newest_file: str | None   # the most recently changed file: shown as "now copying"
    newest_mtime: float

    def grew_since(self, earlier):
        """More bytes, more files, or a file written to more recently: the job is moving."""
        return (self.total_bytes > earlier.total_bytes or self.file_count > earlier.file_count
                or self.newest_mtime > earlier.newest_mtime)


def measure(folders):
    folders = [Path(f) for f in folders]
    name_with_folder = len(folders) > 1   # with several folders, say which one the file is in
    total = count = 0
    newest, newest_mtime = None, 0.0
    for top in folders:
        if not top.is_dir():
            continue  # a destination may not exist until the job creates it
        for relative, stat in _files(top, top):
            total += stat.st_size
            count += 1
            if stat.st_mtime > newest_mtime:
                newest_mtime = stat.st_mtime
                newest = f"{top.name}/{relative}" if name_with_folder else relative
    return FolderSnapshot(total, count, newest, newest_mtime)


def _files(folder, top):
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return  # vanished or unreadable while the job runs: skip, don't stop watching
    for entry in entries:
        try:
            if entry.is_dir(follow_symlinks=False):
                yield from _files(entry.path, top)
            elif entry.is_file(follow_symlinks=False):
                yield Path(entry.path).relative_to(top).as_posix(), _stat(entry)
        except OSError:
            continue  # e.g. a temporary file renamed away mid-count


def _stat(entry):
    return entry.stat(follow_symlinks=False)
