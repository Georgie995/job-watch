"""Building, logging and handing out event messages.

The full command line is never part of an event: it can contain passwords, keys and paths.
Only the job name (given by the person) and the program name are recorded.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 1


def make_event(event, job_name, program, elapsed, progress, last_progress_ago, **extra):
    return {
        "kind": "job_event",
        "schema_version": SCHEMA_VERSION,
        "event_id": uuid.uuid4().hex,
        "sent_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "job_name": job_name,
        "program": program,
        "event": event,
        "elapsed_seconds": round(elapsed),
        "progress": progress,
        "last_progress_seconds_ago": None if last_progress_ago is None else round(last_progress_ago),
        "exit_code": extra.get("exit_code"),
        "error_tail": extra.get("error_tail"),
        "stalled_for_seconds": extra.get("stalled_for_seconds"),
    }


def log_event(log_dir, event):
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / f"{datetime.now():%Y-%m-%d}.jsonl", "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
