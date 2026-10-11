"""The status file: what a job is doing right now, readable from any terminal with `job-watch status`."""

import json
import re
from pathlib import Path


def safe_name(job_name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", job_name).strip("_") or "job"


def write_status(status_dir, record):
    status_dir = Path(status_dir)
    status_dir.mkdir(parents=True, exist_ok=True)
    stem = safe_name(record["job_name"])
    text = json.dumps(record, ensure_ascii=False)
    (status_dir / f"{stem}.json").write_text(text, encoding="utf-8")
    with open(status_dir / f"{stem}.history", "a", encoding="utf-8") as handle:
        handle.write(text + "\n")


def read_statuses(status_dir):
    status_dir = Path(status_dir)
    if not status_dir.exists():
        return []
    records = []
    for path in sorted(status_dir.glob("*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue  # being rewritten at this moment: skip this one
    return records


def describe(record):
    """One readable line, e.g. 'Restore TAPE001: running | 0:42:10 | 1204 files | 812.4 GB | ...'

    Plain ASCII separators, so every terminal shows it the same way.
    """
    p = record["progress"]
    active = record["state"] in ("running", "stalled")
    parts = [f"{record['job_name']}: {record['state']}", duration(record["elapsed_seconds"])]
    if p.get("files") is not None:
        parts.append(f"{p['files']} files" + (f" of {p['total_files']}" if p.get("total_files") else ""))
    if p.get("bytes") is not None:
        parts.append(size(p["bytes"]) + (f" of {size(p['total_bytes'])}" if p.get("total_bytes") else ""))
    if p.get("current_file"):
        # Once the job has ended, nothing is "now copying".
        parts.append(f"{'now copying' if active else 'last file'} {p['current_file']}")
    if p.get("rate_bytes_per_second"):
        parts.append(f"{size(p['rate_bytes_per_second'])}/s")
    if active:
        if record.get("last_progress_seconds_ago") is not None:
            parts.append(f"last progress {duration(record['last_progress_seconds_ago'])} ago")
        eta = record.get("eta_seconds")
        parts.append(f"ETA {duration(eta)}" if eta is not None else "ETA unknown (no total)")
    return " | ".join(parts)


def duration(seconds):
    seconds = int(seconds or 0)
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def size(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000
