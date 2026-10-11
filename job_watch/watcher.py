"""Module 2: run the job, check its progress at regular intervals, and decide what to say.

Events: started, finished, failed, stalled (once per stall), resumed, interrupted.
The watcher never stops, pauses or changes the job. It passes back the job's own exit code.
"""

import collections
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .events import log_event, make_event
from .folder import FolderSnapshot, measure
from .progress import OutputTracker
from .rclone_stats import RcloneTracker
from .status import describe, write_status

ERROR_TAIL_LINES = 10      # configurable default: how much error output a "failed" message carries
ERROR_TAIL_CHARS = 500


@dataclass
class JobConfig:
    name: str
    command: list
    status_dir: Path
    log_dir: Path
    watch_dirs: list = field(default_factory=list)
    expect_bytes: int | None = None
    expect_files: int | None = None
    stall_seconds: float = 600          # Georgi's choice: 10 minutes
    check_seconds: float = 30
    ignore_output: str | None = None


class Watcher:
    def __init__(self, config, sinks=()):
        self.c = config
        self.sinks = list(sinks)            # extra receivers of events, e.g. the alert sender
        self.program = Path(config.command[0]).name if config.command else "?"
        self._lock = threading.Lock()
        self._rclone = RcloneTracker()
        self._output = OutputTracker(config.ignore_output)
        self._errors = collections.deque(maxlen=ERROR_TAIL_LINES)
        self._folder = FolderSnapshot(0, 0, None, 0.0)
        self._stalled = False

    # --- running -------------------------------------------------------------------------

    def run(self):
        self._start = self._last_progress = time.monotonic()
        self._started_at = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            self._proc = subprocess.Popen(self.c.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          text=True, encoding="utf-8", errors="replace", bufsize=1)
        except OSError as error:
            reason = f"could not start {self.program}: {error.strerror or error}"
            self._finish("failed", 127, error_tail=reason)
            return 127

        readers = [threading.Thread(target=self._read, args=(self._proc.stdout, sys.stdout), daemon=True),
                   threading.Thread(target=self._read, args=(self._proc.stderr, sys.stderr), daemon=True)]
        for reader in readers:
            reader.start()
        if not self.c.watch_dirs:
            self._say("note: no --watch folder, so progress is judged from the job's output only")
        self._emit("started")

        while True:
            try:
                done = self._wait(self.c.check_seconds)
            except KeyboardInterrupt:
                # Ctrl-C reaches the job too (normal terminal behaviour); give it a moment to stop.
                try:
                    self._proc.wait(timeout=5)
                except (subprocess.TimeoutExpired, KeyboardInterrupt):
                    pass
                self._finish("interrupted", None, readers=readers)
                return 130
            self._check(final=done)
            if done:
                break

        code = self._proc.returncode
        tail = None if code == 0 else self._error_tail()
        self._finish("finished" if code == 0 else "failed", code, error_tail=tail, readers=readers)
        return code

    def _wait(self, seconds):
        try:
            self._proc.wait(timeout=seconds)
            return True
        except subprocess.TimeoutExpired:
            return False

    def _read(self, stream, echo):
        for line in stream:
            echo.write(line)                   # the job's output still appears on screen
            echo.flush()
            with self._lock:
                if stream is self._proc.stderr:
                    self._errors.append(line.rstrip())
                moved = self._rclone.feed(line)
                if not self._rclone.active and self._output.feed(line):
                    moved = True               # once rclone stats are seen, other output isn't progress
                if moved:
                    self._last_progress = time.monotonic()

    # --- checking --------------------------------------------------------------------------

    def _check(self, final=False):
        now = time.monotonic()
        if self.c.watch_dirs:
            snapshot = measure(self.c.watch_dirs)
            with self._lock:
                if snapshot.grew_since(self._folder):
                    self._last_progress = now
            self._folder = snapshot
        with self._lock:
            last = self._last_progress
        if self._stalled and last > self._stall_declared:
            self._stalled = False
            self._emit("resumed", stalled_for_seconds=round(last - self._stall_began))
        elif not final and not self._stalled and now - last >= self.c.stall_seconds:
            self._stalled, self._stall_began, self._stall_declared = True, last, now
            self._emit("stalled")
        self._write_status("stalled" if self._stalled else "running")

    # --- reporting --------------------------------------------------------------------------

    def _progress(self):
        if self._rclone.active:
            done, files = self._rclone.bytes, self._rclone.files
        elif self.c.watch_dirs:
            done, files = self._folder.total_bytes, self._folder.file_count
        else:
            done, files = None, None
        elapsed = time.monotonic() - self._start
        rate = done / elapsed if done and elapsed > 0 else None
        return {
            "bytes": done,
            "total_bytes": self.c.expect_bytes or self._rclone.total_bytes,
            "files": files,
            "total_files": self.c.expect_files or self._rclone.total_files,
            "current_file": self._folder.newest_file,
            "rate_bytes_per_second": round(rate) if rate else None,
        }

    def _eta(self, progress):
        total, done, rate = progress["total_bytes"], progress["bytes"], progress["rate_bytes_per_second"]
        if not total or done is None or not rate:
            return None                        # no known total (or no speed yet): no guessing
        return round(max(total - done, 0) / rate)

    def _emit(self, event, **extra):
        with self._lock:
            last = self._last_progress
        record = make_event(event, self.c.name, self.program, time.monotonic() - self._start,
                            self._progress(), time.monotonic() - last, **extra)
        log_event(self.c.log_dir, record)
        self._say(f"{event.upper()}: {self.c.name}" + (f" ({extra['error_tail']})" if extra.get("error_tail") else ""))
        for sink in self.sinks:
            sink(record)

    def _finish(self, state, code, error_tail=None, readers=()):
        for reader in readers:
            reader.join(timeout=5)             # make sure the last output lines are counted
        if readers and self.c.watch_dirs:
            self._folder = measure(self.c.watch_dirs)
        if self._stalled and readers:
            self._check(final=True)            # a job that recovered at the very end
        self._emit(state, exit_code=code, error_tail=error_tail)
        self._write_status(state, exit_code=code)

    def _write_status(self, state, exit_code=None):
        progress = self._progress()
        with self._lock:
            last = self._last_progress
        record = {"job_name": self.c.name, "program": self.program, "state": state,
                  "started_at": self._started_at,
                  "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                  "elapsed_seconds": round(time.monotonic() - self._start), "progress": progress,
                  "last_progress_seconds_ago": round(time.monotonic() - last),
                  "eta_seconds": self._eta(progress) if state in ("running", "stalled") else None,
                  "exit_code": exit_code}
        write_status(self.c.status_dir, record)
        if state in ("running", "stalled"):
            self._say(describe(record))

    def _error_tail(self):
        with self._lock:
            text = "\n".join(line for line in self._errors if line)
        return text[-ERROR_TAIL_CHARS:] or None

    @staticmethod
    def _say(text):
        print(f"[job-watch] {text}", file=sys.stderr, flush=True)
