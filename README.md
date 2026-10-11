# job-watch

Watches long jobs (tape restores and writes, cloud transfers) and says **once** when they finish, fail, **stall**, or start moving again. It shows plainly what's happening while they run. It never stops or changes the job.

Alerts go through [delivery-ops-hub](https://github.com/Georgie995/delivery-ops-hub), the same n8n workflow, log and alert cards as delivery checks.

## The problem

Long jobs run as Linux commands for hours. While they run, the operator can't easily see:
- which file is being copied;
- how far through the job it is;
- whether it's moving at all.

So people list folders "blindly" to guess. Worse, a job can **stall silently** and only fail much later. In one real case, a tape copy reached a bad section, stalled, and errored out long afterwards ([domain notes](docs/domain-notes.md)).

## How it works

```
python -m job_watch run --name "Restore TAPE001" --watch /restore/TAPE001 -- <restore command>
python -m job_watch run --name "Upload ShowA" -- rclone copy <src> <dst> --use-json-log --stats 30s
python -m job_watch status          # from any terminal: what every job is doing
```

The job runs **exactly as given** after `--`, and its output still appears on screen. Every 30 seconds the watcher looks for **progress**:

| Signal | Counts as progress when… |
|---|---|
| **rclone's own stats** (`--use-json-log`) | the transferred `bytes` count **rises**. rclone prints stats even when stuck, so a repeated line isn't progress. |
| **A watched folder** (`--watch`) | more bytes, more files, or a file written to more recently. The newest file is shown as "now copying". |
| **Output lines** | a new line that isn't a heartbeat you've listed with `--ignore-output` (e.g. "still running") |

**Events, each logged once and sent to delivery-ops-hub:**
- `started`: logged only.
- `finished`: an alert.
- `failed`: an alert, with the exit code and the last error lines.
- `stalled`: an alert after 10 minutes with no progress. The watcher keeps watching.
- `resumed`: an alert, with how long it was stalled.
- `interrupted`: an alert. Ctrl-C stops the job too, so the outcome is unknown.

**Safe by design:**
- **It never stops, pauses or changes the job.**
- **It exits with the job's own exit code** (127 if the command couldn't start, 130 if interrupted), so anything that calls it behaves as before.
- **The full command line is never logged or sent.** Commands, especially rclone ones, can contain passwords, keys or internal paths. Only the job's name and the program's name are recorded.
- **An ETA is shown only when the total is known** (rclone's own total, or `--expect-bytes`). Tape restore sizes often aren't known until the tape is indexed, so it doesn't guess.
- **Alerting can never fail a job.** If delivery-ops-hub, its address or the secret is missing, job-watch says "alerts are off (reason)" once and logs locally. If n8n is unreachable, events wait in the outbox, and delivery-ops-hub's `resend` command delivers them later.

## Example (real output, synthetic job)

A made-up restore that goes quiet for a moment and then recovers (the stall time is shortened for the demo):

```
[job-watch] STARTED: Restore TAPE001
[job-watch] Restore TAPE001: running | 0:00:01 | 2 files | 2.0 KB | now copying a_0.mov | 3.2 KB/s | last progress 0:00:00 ago | ETA unknown (no total)
[job-watch] STALLED: Restore TAPE001
[job-watch] Restore TAPE001: stalled | 0:00:02 | 2 files | 2.0 KB | now copying a_0.mov | 811 B/s | last progress 0:00:02 ago | ETA unknown (no total)
[job-watch] RESUMED: Restore TAPE001
[job-watch] Restore TAPE001: running | 0:00:03 | 4 files | 4.0 KB | now copying b_1.mov | 1.3 KB/s | last progress 0:00:00 ago | ETA unknown (no total)
[job-watch] FINISHED: Restore TAPE001
```

In delivery-ops-hub, the stall becomes an alert card (dry run): **"STALLED: Restore TAPE001. No progress for 0:10:00. The job is still running; nothing has been stopped."** It includes the program, the time so far, files and data done, and the last file. Each event is also a row in `runtime/logs/job-events.csv`.

## Set-up

- **Requirements:** Python 3.11+, standard library only.
- **Run it:** `python -m job_watch run …` from this folder. No install step is needed.
- **Alerts:** copy `job-watch.example.toml` to `job-watch.toml`, point it at your delivery-ops-hub folder and webhook, and set `OPS_HUB_WEBHOOK_SECRET`.
- **Tests:**
  ```
  python -m pytest
  ```
  37 tests using tiny fake jobs that copy, stall, recover, fail, print heartbeats, or imitate rclone repeating the same numbers. In tests, a stall is 1 second instead of 10 minutes. The alert tests run when delivery-ops-hub sits next to this folder. One end-to-end test sends a real stalling job's events into a running n8n.

## Known limits

- **Built for Linux, but developed and tested on Windows** with fake jobs. It avoids Windows-only and Linux-only features. A run on Linux with real jobs is still to be done.
- **Large folders:** `--watch` walks the folder at each check, so very large folders may need a longer `--check-seconds`.
- **Silent jobs:** a job that prints nothing, with no folder watched, can only be judged by its exit code. When no folder is watched, the watcher prints a note at the start.
- **Ctrl-C** stops the job too, which is normal terminal behaviour. Jobs that survive closing the terminal are out of scope.
- **Speed** is the average since the start, not the current speed.

## Documentation

- [DESIGN.md](docs/DESIGN.md)
- [DECISIONS.md](docs/DECISIONS.md)
- [walkthrough.md](docs/walkthrough.md): plain-English explanation of each part
- [domain-notes.md](docs/domain-notes.md)

All test data is synthetic. No client names, project or tape codes, hostnames or internal paths appear anywhere.

## AI assistance

> **DRAFT. Georgi to confirm or correct before publishing.**

The code in this repository was written with an AI coding assistant (Claude, by Anthropic). I did not write the Python by hand.

What I did:

- **The idea came from my own work:** babysitting long tape and cloud jobs, listing folders blindly to guess progress, and a tape copy that stalled before it crashed.
- **I set the requirements:**
  - which jobs it must handle (Linux command-line tape tools and rclone);
  - that progress can't be seen without watching;
  - that tape restore sizes aren't known until indexing;
  - a 10-minute stall time;
  - alert only, never stop the job;
  - alerts through my existing delivery-ops-hub.
- **I approved the design** before any code was written. The decisions are logged in `docs/DECISIONS.md`.
- **I learned how it works** through a plain-English explanation of each part.

## Licence

[MIT](LICENSE) © 2026 Georgi Stoyanov
