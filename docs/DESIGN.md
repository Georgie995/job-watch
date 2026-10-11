# job-watch: design

Status: **Approved by Georgi on 2026-10-11** (with the proposed alert events, Ctrl-C behaviour and the delivery-ops-hub branch).

## 1. What problem this solves

Long jobs (tape restores and writes, cloud uploads and downloads) run as Linux commands for minutes to hours. While they run, the operator can't easily see:
- which file is being copied;
- how far through the job it is;
- whether it's still moving at all.

So people keep listing folders "blindly" to guess. A job can also **stall silently** and only fail much later. In domain note F9, a tape copy stalled at a bad section, then errored out and crashed.

job-watch runs the job **through a watcher**. It:
- shows plainly what's happening;
- tells people once when the job **finishes**, **fails** or **stalls** (and when a stalled job **resumes**);
- records everything.

It **never stops, pauses or changes the job.**

## 2. Words used in this document

| Term | Meaning |
|---|---|
| **Job** | The long command being watched, e.g. a restore or an `rclone copy`. |
| **Exit code** | The number a command returns when it ends: `0` means success, anything else means failure. |
| **Progress signal** | Evidence the job is moving: the destination folder growing, rclone's transferred-bytes count going up, or new output lines. |
| **Stall** | No progress signal at all for the stall time (default 10 minutes). |
| **Heartbeat output** | Text a program prints regularly even when nothing is moving (e.g. "still running…"). It must not count as progress. |
| **ETA** | Estimated time remaining. Only possible when the total size is known. |
| **Webhook** | delivery-ops-hub's n8n address that receives events and raises alerts (project 2). |

## 3. How it's used

```
job-watch run --name "Restore TAPE001" --watch /restore/TAPE001 -- <restore command and its arguments>
job-watch run --name "Upload ShowA" -- rclone copy <source> <destination> --use-json-log --stats 30s
job-watch status                       # what's running now, from another terminal
```

- Everything after `--` is the job, run **exactly as given**. There's no shell, so pipes (`|`) need `bash -c "…"`. Its output still appears on screen as normal.
- **job-watch exits with the job's own exit code**, so scripts that call it behave exactly as before.
- **Optional:**
  - `--watch DIR` (repeatable): folders whose growth counts as progress (e.g. the restore destination);
  - `--expect-bytes N` / `--expect-files N`: the known total, which allows an ETA;
  - `--stall-minutes M`;
  - `--ignore-output REGEX`: heartbeat lines that don't count as progress;
  - `--no-alerts`: log only.

## 4. What it watches (progress signals)

Every check (default every 30 seconds):

| Signal | Used when | Counts as progress if… |
|---|---|---|
| **rclone stats** | the job is rclone with `--use-json-log` | `stats.bytes` (transferred so far) went up. rclone documents this format: with `--use-json-log`, stats lines carry a `stats` field (`bytes`, `totalBytes`, `transfers`, `totalTransfers`), the same as its `core/stats` call. Because rclone prints stats even when nothing moves, **its other output is not counted as progress.** |
| **Watched folder** | `--watch DIR` was given | the total size or file count under the folder went up. The newest-changed file is shown as **"now copying"**. |
| **Output lines** | otherwise | a new output line that doesn't match `--ignore-output` |

**Totals and ETA:** from rclone's `totalBytes` / `totalTransfers`, or from `--expect-bytes` / `--expect-files`. Without a known total, it shows progress so far and speed, and **no ETA**. Tape restore sizes often aren't known until the tape is indexed, so it doesn't pretend.

## 5. What it tells people

**On screen, refreshed each check** (and in `job-watch status`):
```
Restore TAPE001 · 0:42:10 · 1,204 files · 812.4 GB · now copying ShowA/Reel04/clip_0457.mov
  410 MB/s · last progress 0:00:40 ago · ETA unknown (no total given)
```

**Events**, each one logged locally and sent to delivery-ops-hub:

| Event | When | Teams alert? (proposal) |
|---|---|---|
| `started` | job starts | no, logged only |
| `finished` | exit code 0 | **yes**, quiet: "finished in 2:14:05, 4,812 files, 3.1 TB" |
| `failed` | exit code ≠ 0, or the command couldn't start | **yes**: exit code plus the last lines of error output (max 500 characters) |
| `stalled` | no progress for the stall time | **yes**: "no progress for 10 min; last progress at 14:02; last file …" (once per stall) |
| `resumed` | progress returns after a stall | **yes**: "resumed after 23 min" |
| `interrupted` | the watcher was stopped (Ctrl-C) | **yes**: "watcher stopped; job outcome unknown" |

**Privacy and safety:** the full command line is **never sent or logged**, because it can contain passwords, keys or internal paths (rclone commands often do). Only the job name you gave and the program name (e.g. `rclone`) are sent.

## 6. Status file and logs

- **Status:** `job-watch-status/<job name>.json`, rewritten every check. `job-watch status` prints every job in it.
- **Log:** `job-watch-logs/<date>.jsonl`, one line per event.
- Both folders are git-ignored. Nothing in the watched folders is ever written to.

## 7. Alerts through delivery-ops-hub

- **Reusing the sender, not copying it.** job-watch **imports** delivery-ops-hub's `post_json` and outbox from the folder named in its settings. If the webhook can't be reached, events wait in the outbox and are re-sent later, exactly like project 2.
- **Fallback:** if delivery-ops-hub isn't available, job-watch says so once and **logs only**. It never fails a job because alerting failed.
- **The message** is a new event type in delivery-ops-hub's format (`"kind": "job_event"`, `schema_version` 1): job name, program, event, elapsed time, progress (bytes, files, current file, speed, total if known), last progress time, exit code, and short error text.
- **The workflow** gets a small new branch: validate → append a row to a **separate** log, `runtime/logs/job-events.csv` → for alerting events, build and save (dry-run) a Teams card, like delivery checks. The existing delivery-check branch is unchanged, and its live tests must still pass.

## 8. Settings (`job-watch.toml`, git-ignored; example committed)

- `ops_hub_path`, `webhook_url`, `outbox_dir`;
- `check_seconds` (30), `stall_minutes` (10, Georgi's choice);
- the webhook secret comes from the same environment variable as project 2: `OPS_HUB_WEBHOOK_SECRET`.

## 9. Code layout

- `progress.py`: the three progress signals, and how they're read.
- `folder.py`: folder size/count and the "now copying" file.
- `rclone_stats.py`: reading rclone's JSON stats lines.
- `watcher.py`: runs the job, checks every interval, decides started / stalled / resumed / finished / failed.
- `status.py`, `events.py`: status file, local log, sending via delivery-ops-hub.
- `cli.py`: `run` and `status`.

Python standard library only. Nothing new to install, apart from pytest, which is already installed for the other projects.

## 10. Testing

- **Fake jobs:** tiny Python scripts that copy files, print rclone-style JSON stats, go silent (stall), recover, or fail. They run in seconds, with the stall time set in seconds for tests.
- **Every event is triggered by a fake job.** Checks include:
  - **heartbeat output doesn't hide a stall**, and rclone's repeated stats don't hide one either;
  - the exit code is passed through;
  - the full command never appears in any log, status file or message.
- **Alert sending** is tested against the same in-test web server as project 2. The new n8n branch gets live tests against the running n8n, like project 2's.

## 11. Build order (each ends with a plain-English explanation)

1. Progress signals: folder, rclone stats, output lines.
2. The watcher (events, status file, log, exit codes).
3. Alerts: sending through delivery-ops-hub, plus the new n8n branch with live tests.
4. README (AI-assistance statement for approval), safety search, clean-copy test, publish, profile update, and the end-of-project quiz.

## 12. Known limits from the start

- **Target is Linux.** It's developed and tested on Windows with fake jobs, and the code avoids Windows-only and Linux-only features. A real Linux run is still to be done.
- **Large folders take longer to measure.** With `--watch` on a folder of hundreds of thousands of files, each check walks the folder, so the check interval may need raising.
- **Ctrl-C** in the terminal stops the job too, which is normal terminal behaviour, and the watcher reports `interrupted`. Running jobs that survive closing the terminal is out of scope.
- **Commands that print nothing**, with nothing watched, can only be judged by their exit code. The stall check needs at least one progress signal, and the watcher warns at the start if there isn't one.
