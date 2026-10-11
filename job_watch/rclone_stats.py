"""Progress signal 2: rclone's own transfer counts.

With --use-json-log, rclone writes its progress as JSON lines containing a "stats" field
(bytes, totalBytes, transfers, totalTransfers), the same as its core/stats call (rclone docs).
rclone prints these lines regularly even when nothing is moving, so only a RISING byte count
counts as progress.
"""

import json


def parse_stats(line):
    text = line.strip()
    if not text.startswith("{"):
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    stats = data.get("stats") if isinstance(data, dict) else None
    return stats if isinstance(stats, dict) else None


class RcloneTracker:
    def __init__(self):
        self.active = False       # True once any stats line has been seen
        self.bytes = 0
        self.total_bytes = None
        self.files = 0
        self.total_files = None

    def feed(self, line):
        stats = parse_stats(line)
        if stats is None:
            return False
        self.active = True
        done = int(stats.get("bytes") or 0)
        progressed = done > self.bytes
        self.bytes = max(self.bytes, done)
        self.total_bytes = stats.get("totalBytes", self.total_bytes)
        self.files = int(stats.get("transfers") or self.files)
        self.total_files = stats.get("totalTransfers", self.total_files)
        return progressed
