"""Module 2 tests: the one-line status description."""

from job_watch.status import describe


def record(state, **progress):
    base = {"bytes": 4000, "total_bytes": None, "files": 4, "total_files": None,
            "current_file": "ShowA/b_1.mov", "rate_bytes_per_second": 1200}
    return {"job_name": "Restore TAPE001", "state": state, "elapsed_seconds": 3723,
            "progress": {**base, **progress}, "last_progress_seconds_ago": 40, "eta_seconds": None}


def test_running_job_shows_what_is_copying_now():
    line = describe(record("running"))
    assert line == ("Restore TAPE001: running | 1:02:03 | 4 files | 4.0 KB | now copying ShowA/b_1.mov | "
                    "1.2 KB/s | last progress 0:00:40 ago | ETA unknown (no total)")


def test_finished_job_shows_last_file_and_no_eta():
    line = describe(record("finished"))
    assert "now copying" not in line and "ETA" not in line and "last progress" not in line
    assert "last file ShowA/b_1.mov" in line


def test_status_line_is_plain_ascii_so_any_terminal_shows_it():
    assert describe(record("running", current_file="a.mov")).isascii()
