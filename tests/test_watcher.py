"""Module 2 tests: the watcher, run against tiny fake jobs (stall time 1 second instead of 10 minutes)."""

import json
import sys
from pathlib import Path

import pytest

from job_watch import cli
from job_watch.watcher import JobConfig, Watcher

JOBS = str(Path(__file__).with_name("jobs.py"))


def job(*args):
    return [sys.executable, JOBS, *[str(a) for a in args]]


def watch(tmp_path, command, **options):
    events = []
    config = JobConfig(name=options.pop("name", "Test job"), command=command,
                       status_dir=tmp_path / "status", log_dir=tmp_path / "logs",
                       stall_seconds=options.pop("stall_seconds", 1.0),
                       check_seconds=options.pop("check_seconds", 0.2), **options)
    code = Watcher(config, sinks=[events.append]).run()
    return code, events


def names(events):
    return [e["event"] for e in events]


def test_a_successful_job_reports_started_then_finished_with_totals(tmp_path):
    dest = tmp_path / "restore"
    code, events = watch(tmp_path, job("copy", dest, 5, 0.05), watch_dirs=[dest])
    assert code == 0
    assert names(events) == ["started", "finished"]
    done = events[-1]
    assert done["progress"]["files"] == 5 and done["progress"]["bytes"] == 5000
    assert done["exit_code"] == 0 and done["job_name"] == "Test job"


def test_a_failing_job_reports_failed_with_its_exit_code_and_error_text(tmp_path):
    code, events = watch(tmp_path, job("fail"))
    assert code == 3                                       # the job's own exit code is passed back
    assert names(events) == ["started", "failed"]
    assert events[-1]["exit_code"] == 3
    assert "drive not ready" in events[-1]["error_tail"]


def test_a_command_that_cannot_start_is_reported_as_failed(tmp_path):
    code, events = watch(tmp_path, ["no-such-program-xyz", "--flag"])
    assert code == 127                                     # the usual "command not found" code
    assert names(events) == ["failed"]
    assert "could not start" in events[0]["error_tail"]


def test_a_stall_is_reported_once_and_a_recovery_is_reported_as_resumed(tmp_path):
    dest = tmp_path / "restore"
    code, events = watch(tmp_path, job("pause", dest, 2.5), watch_dirs=[dest])
    assert code == 0
    assert names(events) == ["started", "stalled", "resumed", "finished"]   # one stall alert, not many
    assert events[2]["stalled_for_seconds"] >= 1


def test_heartbeat_output_does_not_hide_a_stall_when_it_is_ignored(tmp_path):
    _, events = watch(tmp_path, job("heartbeat", 1.8), ignore_output=r"still running")
    assert "stalled" in names(events)


def test_without_the_ignore_pattern_heartbeat_lines_look_like_progress(tmp_path):
    # Documents why --ignore-output exists.
    _, events = watch(tmp_path, job("heartbeat", 1.8))
    assert "stalled" not in names(events)


def test_rclone_repeating_the_same_numbers_is_a_stall_and_its_totals_are_used(tmp_path):
    _, events = watch(tmp_path, job("rclone", 1.8))
    assert names(events) == ["started", "stalled", "resumed", "finished"]
    final = events[-1]["progress"]
    assert (final["bytes"], final["total_bytes"], final["total_files"]) == (1000, 1000, 4)


def test_job_output_still_appears_on_screen(tmp_path, capsys):
    watch(tmp_path, job("copy", tmp_path / "d", 2, 0.01))
    assert "copied clip_0001.mov" in capsys.readouterr().out


def test_the_full_command_line_is_never_recorded(tmp_path):
    secret = "--password=SUPERSECRET123"
    _, events = watch(tmp_path, job("copy", tmp_path / "d", 2, 0.01) + [secret])
    stored = json.dumps(events)
    stored += "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "logs").glob("*"))
    stored += "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "status").glob("*"))
    assert "SUPERSECRET123" not in stored
    assert all(e["program"] == Path(sys.executable).name for e in events)


def test_every_event_is_logged_and_the_status_file_shows_the_outcome(tmp_path):
    _, events = watch(tmp_path, job("fail"), name="Restore TAPE001")
    [log] = (tmp_path / "logs").glob("*.jsonl")
    assert [json.loads(line)["event"] for line in log.read_text(encoding="utf-8").splitlines()] == names(events)
    status = json.loads((tmp_path / "status" / "Restore_TAPE001.json").read_text(encoding="utf-8"))
    assert status["state"] == "failed" and status["job_name"] == "Restore TAPE001"


def test_eta_is_given_only_when_the_total_is_known(tmp_path):
    dest = tmp_path / "d"
    _, without = watch(tmp_path, job("copy", dest, 6, 0.25), watch_dirs=[dest], name="no total")
    status = json.loads((tmp_path / "status" / "no_total.json").read_text(encoding="utf-8"))
    assert status["eta_seconds"] is None
    dest2 = tmp_path / "d2"
    watch(tmp_path, job("copy", dest2, 6, 0.25), watch_dirs=[dest2], name="with total", expect_bytes=60_000)
    history = (tmp_path / "status" / "with_total.history").read_text(encoding="utf-8").splitlines()
    assert any(json.loads(h)["eta_seconds"] is not None for h in history)


def test_ctrl_c_reports_interrupted(tmp_path, monkeypatch):
    calls = {"n": 0}
    real_wait = Watcher._wait

    def interrupt_once(self, seconds):
        calls["n"] += 1
        if calls["n"] == 2:
            raise KeyboardInterrupt
        return real_wait(self, seconds)

    monkeypatch.setattr(Watcher, "_wait", interrupt_once)
    code, events = watch(tmp_path, job("tick", 1.0))
    assert code == 130
    assert names(events)[-1] == "interrupted"


# --- The command line --------------------------------------------------------------------

def test_run_and_status_commands(tmp_path, capsys):
    dest = tmp_path / "restore"
    code = cli.main(["run", "--name", "Restore TAPE001", "--watch", str(dest), "--stall-minutes", "1",
                     "--status-dir", str(tmp_path / "status"), "--log-dir", str(tmp_path / "logs"),
                     "--no-alerts", "--", *job("copy", dest, 3, 0.01)])
    assert code == 0
    capsys.readouterr()
    assert cli.main(["status", "--status-dir", str(tmp_path / "status")]) == 0
    out = capsys.readouterr().out
    assert "Restore TAPE001" in out and "finished" in out and "3 files" in out


def test_run_without_a_command_is_a_usage_error(tmp_path, capsys):
    assert cli.main(["run", "--name", "x"]) == 2
    assert "after --" in capsys.readouterr().err
