"""Module 1 tests: the three progress signals."""

import json
import os
import time

from job_watch import folder
from job_watch.folder import measure
from job_watch.progress import OutputTracker
from job_watch.rclone_stats import RcloneTracker, parse_stats


def make(path, size=10, mtime=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


# --- Watched folder ------------------------------------------------------------------

def test_folder_totals_count_every_file_in_every_subfolder(tmp_path):
    make(tmp_path / "ShowA/Reel01/a.mov", 100)
    make(tmp_path / "ShowA/Reel02/b.mov", 50)
    snap = measure([tmp_path])
    assert (snap.total_bytes, snap.file_count) == (150, 2)


def test_now_copying_is_the_most_recently_changed_file(tmp_path):
    make(tmp_path / "ShowA/a.mov", mtime=1_000_000)
    make(tmp_path / "ShowA/b.mov", mtime=2_000_000)
    assert measure([tmp_path]).newest_file == "ShowA/b.mov"


def test_a_folder_that_does_not_exist_yet_measures_as_empty(tmp_path):
    # A restore destination may only be created once the job starts.
    snap = measure([tmp_path / "not_created_yet"])
    assert (snap.total_bytes, snap.file_count, snap.newest_file) == (0, 0, None)


def test_growth_is_progress_and_no_change_is_not(tmp_path):
    make(tmp_path / "a.mov", 10, mtime=1_000_000)
    before = measure([tmp_path])
    assert not measure([tmp_path]).grew_since(before)
    make(tmp_path / "b.mov", 10)
    assert measure([tmp_path]).grew_since(before)


def test_a_file_being_rewritten_in_place_counts_as_progress(tmp_path):
    # Same size and count, but written to again (newer modification time).
    f = make(tmp_path / "a.mov", 10, mtime=1_000_000)
    before = measure([tmp_path])
    os.utime(f, (2_000_000, 2_000_000))
    assert measure([tmp_path]).grew_since(before)


def test_files_vanishing_mid_count_are_skipped_not_fatal(tmp_path, monkeypatch):
    make(tmp_path / "a.mov", 10)
    make(tmp_path / "temp.part", 10)
    real_stat = folder._stat

    def vanishing(entry):
        if entry.name == "temp.part":
            raise FileNotFoundError(2, "gone")  # a temporary file renamed away mid-count
        return real_stat(entry)

    monkeypatch.setattr(folder, "_stat", vanishing)
    assert measure([tmp_path]).file_count == 1


def test_several_watched_folders_are_added_together_and_named(tmp_path):
    make(tmp_path / "one/a.mov", 10, mtime=1_000_000)
    make(tmp_path / "two/b.mov", 20, mtime=2_000_000)
    snap = measure([tmp_path / "one", tmp_path / "two"])
    assert (snap.total_bytes, snap.file_count) == (30, 2)
    assert snap.newest_file == "two/b.mov"


# --- rclone stats -------------------------------------------------------------------------

def stats_line(bytes_done, total=1000, transfers=1, total_transfers=4):
    # Shape documented by rclone for --use-json-log: a "stats" field like its core/stats call.
    return json.dumps({"level": "info", "msg": "stats", "source": "accounting/stats.go:500",
                       "stats": {"bytes": bytes_done, "totalBytes": total, "transfers": transfers,
                                 "totalTransfers": total_transfers, "speed": 12.5},
                       "time": "2026-10-11T14:00:00Z"})


def test_rclone_stats_lines_are_recognised():
    stats = parse_stats(stats_line(250))
    assert (stats["bytes"], stats["totalBytes"], stats["transfers"], stats["totalTransfers"]) == (250, 1000, 1, 4)


def test_other_lines_are_not_stats():
    assert parse_stats("2026/10/11 14:00:00 INFO  : a.mov: Copied (new)") is None
    assert parse_stats('{"level": "info", "msg": "Copied (new)"}') is None
    assert parse_stats("not json at all {") is None


def test_rising_bytes_are_progress_but_repeated_stats_are_not():
    tracker = RcloneTracker()
    assert tracker.feed(stats_line(100)) is True
    assert tracker.feed(stats_line(100)) is False   # rclone repeats stats while stalled: not progress
    assert tracker.feed(stats_line(400)) is True
    assert (tracker.bytes, tracker.total_bytes, tracker.files, tracker.total_files) == (400, 1000, 1, 4)


def test_tracker_knows_whether_it_has_seen_stats():
    tracker = RcloneTracker()
    tracker.feed("plain text output")
    assert tracker.active is False                   # e.g. --use-json-log was forgotten
    tracker.feed(stats_line(1))
    assert tracker.active is True


# --- Output lines ---------------------------------------------------------------------------

def test_new_output_lines_are_progress():
    assert OutputTracker().feed("Restored ShowA/Reel01/a.mov") is True


def test_blank_lines_and_heartbeat_lines_are_not_progress():
    tracker = OutputTracker(ignore=r"still running|waiting for drive")
    assert tracker.feed("") is False
    assert tracker.feed("   ") is False
    assert tracker.feed("Job still running...") is False
    assert tracker.feed("Waiting for drive") is False    # case doesn't matter
    assert tracker.feed("Restored b.mov") is True
