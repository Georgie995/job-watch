"""The command line.

    job-watch run --name "Restore TAPE001" [--watch DIR] [options] -- <the job's command>
    job-watch status

`run` exits with the job's own exit code (127 if it couldn't start, 130 if interrupted).
"""

import argparse
import os
import sys

from .alerts import AlertSender
from .settings import SettingsError, load_settings
from .status import describe, read_statuses
from .watcher import JobConfig, Watcher


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    command = []
    if "--" in argv:
        split = argv.index("--")
        argv, command = argv[:split], argv[split + 1:]
    args = _parser().parse_args(argv)

    if args.what == "status":
        records = read_statuses(args.status_dir)
        print("\n".join(describe(r) for r in records) if records else "No jobs recorded.")
        return 0

    if not command:
        print("job-watch: error: give the job's command after --, e.g. job-watch run --name X -- rclone copy …",
              file=sys.stderr)
        return 2
    try:
        settings = load_settings(args.config)
    except SettingsError as error:
        print(f"job-watch: error: {error}", file=sys.stderr)
        return 2
    sinks = []
    if not args.no_alerts:
        sender = AlertSender(settings, os.environ.get("OPS_HUB_WEBHOOK_SECRET", "").strip() or _saved_user_secret())
        if sender.enabled:
            sinks.append(sender)
        else:
            print(f"[job-watch] alerts are off ({sender.reason}); events are logged locally only", file=sys.stderr)
    config = JobConfig(name=args.name, command=command, status_dir=args.status_dir, log_dir=args.log_dir,
                       watch_dirs=args.watch or [], expect_bytes=args.expect_bytes, expect_files=args.expect_files,
                       stall_seconds=args.stall_minutes * 60, check_seconds=args.check_seconds,
                       ignore_output=args.ignore_output)
    try:
        return Watcher(config, sinks=sinks).run()
    finally:
        for sink in sinks:
            sink.close()  # send anything still queued before exiting


def _saved_user_secret():
    """On Windows, a terminal opened before the secret was saved can't see it; read the saved value.
    (Georgi hit exactly this in project 2's hands-on run.) Elsewhere: only the environment counts."""
    if os.name != "nt":
        return ""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return str(winreg.QueryValueEx(key, "OPS_HUB_WEBHOOK_SECRET")[0]).strip()
    except OSError:
        return ""


def _parser():
    parser = argparse.ArgumentParser(prog="job-watch",
                                     description="Watch a long job and say once when it finishes, fails, stalls or resumes.")
    commands = parser.add_subparsers(dest="what", required=True)
    run = commands.add_parser("run", help="run a job under the watcher (put the job's command after --)")
    run.add_argument("--name", required=True, help="a name people will recognise, e.g. 'Restore TAPE001'")
    run.add_argument("--watch", action="append", help="folder whose growth counts as progress (repeatable)")
    run.add_argument("--expect-bytes", type=int, help="known total size, which allows an ETA")
    run.add_argument("--expect-files", type=int, help="known total number of files")
    run.add_argument("--stall-minutes", type=float, default=10, help="minutes without progress = stalled (default 10)")
    run.add_argument("--check-seconds", type=float, default=30, help="how often to check (default 30)")
    run.add_argument("--ignore-output", help="regular expression for heartbeat lines that aren't progress")
    run.add_argument("--no-alerts", action="store_true", help="log only; don't send alerts")
    run.add_argument("--config", default="job-watch.toml", help="settings file (default: %(default)s)")
    for sub in (run, commands.add_parser("status", help="show what every recorded job is doing")):
        sub.add_argument("--status-dir", default="job-watch-status")
    run.add_argument("--log-dir", default="job-watch-logs")
    return parser
