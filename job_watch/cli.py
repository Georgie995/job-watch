"""The command line.

    job-watch run --name "Restore TAPE001" [--watch DIR] [options] -- <the job's command>
    job-watch status

`run` exits with the job's own exit code (127 if it couldn't start, 130 if interrupted).
"""

import argparse
import sys

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
    config = JobConfig(name=args.name, command=command, status_dir=args.status_dir, log_dir=args.log_dir,
                       watch_dirs=args.watch or [], expect_bytes=args.expect_bytes, expect_files=args.expect_files,
                       stall_seconds=args.stall_minutes * 60, check_seconds=args.check_seconds,
                       ignore_output=args.ignore_output)
    return Watcher(config).run()


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
    for sub in (run, commands.add_parser("status", help="show what every recorded job is doing")):
        sub.add_argument("--status-dir", default="job-watch-status")
    run.add_argument("--log-dir", default="job-watch-logs")
    return parser
