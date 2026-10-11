"""Tiny fake 'long jobs' for the tests. Each one runs in a few seconds.

    python jobs.py copy DEST COUNT DELAY        write COUNT files into DEST, DELAY seconds apart
    python jobs.py pause DEST QUIET             write 2 files, go silent for QUIET seconds, write 2 more
    python jobs.py fail                         print an error and exit with code 3
    python jobs.py heartbeat SECONDS            print "still running" repeatedly, nothing else
    python jobs.py rclone STALL                 print rclone-style JSON stats, repeat the same bytes for STALL seconds
    python jobs.py tick SECONDS                 print a short line every 0.1 seconds
"""

import json
import sys
import time
from pathlib import Path


def stats(done, total=1000):
    print(json.dumps({"level": "info", "msg": "stats", "stats": {"bytes": done, "totalBytes": total,
                                                                  "transfers": done // 250,
                                                                  "totalTransfers": 4}}), flush=True)


def main(kind, *args):
    if kind == "copy":
        dest, count, delay = Path(args[0]), int(args[1]), float(args[2])
        dest.mkdir(parents=True, exist_ok=True)
        for n in range(count):
            (dest / f"clip_{n:04d}.mov").write_bytes(b"x" * 1000)
            print(f"copied clip_{n:04d}.mov", flush=True)
            time.sleep(delay)
    elif kind == "pause":
        dest, quiet = Path(args[0]), float(args[1])
        dest.mkdir(parents=True, exist_ok=True)
        for n in range(2):
            (dest / f"a_{n}.mov").write_bytes(b"x" * 1000)
        time.sleep(quiet)                         # the "bad section of tape"
        for n in range(2):
            (dest / f"b_{n}.mov").write_bytes(b"x" * 1000)
            time.sleep(0.3)
    elif kind == "fail":
        print("reading block 51200", flush=True)
        print("error: drive not ready", file=sys.stderr, flush=True)
        sys.exit(3)
    elif kind == "heartbeat":
        end = time.time() + float(args[0])
        while time.time() < end:
            print("Job still running...", flush=True)
            time.sleep(0.1)
    elif kind == "rclone":
        stats(250)
        stats(500)
        end = time.time() + float(args[0])
        while time.time() < end:                 # rclone keeps printing while stuck
            stats(500)
            time.sleep(0.1)
        stats(1000)
    elif kind == "tick":
        end = time.time() + float(args[0])
        while time.time() < end:
            print("tick", flush=True)
            time.sleep(0.1)


if __name__ == "__main__":
    main(*sys.argv[1:])
