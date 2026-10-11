# Decisions

Each entry records the decision, the alternatives considered and why this one was chosen.

## 2026-10-11: Idea D from the brainstorm

- **Source:** chosen by Georgi from `research/ideas-backlog.md`. Its basis is his own experience: babysitting long jobs, and a tape copy that stalled and then crashed (F9).

## 2026-10-11: Watch commands, and optionally folders

- **The jobs:** Georgi's long jobs were Linux commands, a mix of standard copy tools and tape software command-line tools, plus rclone for cloud transfers.
- **Decision:** the job is started through job-watch, which always knows when and how it ended (the exit code). Progress comes from rclone's stats, from watched folders, or from output lines.
- **Ruled out:** watching a GUI's progress bar isn't possible, and wasn't needed.

## 2026-10-11: Stall after 10 minutes; alert only

- **Decision:** Georgi's choices. A stall raises one alert and keeps watching, with a "resumed" alert if progress returns. The watcher never stops or changes the job; a person decides.

## 2026-10-11: Alerts through delivery-ops-hub

- **Decision:** reuse project 2's n8n workflow, with a new "job event" branch, a separate CSV log and the same alert cards (Georgi's choice).
- **Sender reused, not copied:** delivery-ops-hub's sender is imported, not copied. If it's unavailable, job-watch logs locally and never fails a job because of alerting.

## 2026-10-11: ETA only when the total is known

- **Why:** Georgi said the total size of a tape restore usually isn't known until the tape has been indexed. An ETA without a known total would be a guess, so none is shown.

## 2026-10-11: rclone output isn't progress; its byte count is

- **Why:** rclone prints stats lines regularly even when nothing is moving. With `--use-json-log`, its documented stats carry `bytes` and `totalBytes` (rclone docs, checked 2026-10-11). Only a rising `bytes` counts.

## 2026-10-11: Never log or send the full command line

- **Why:** commands (rclone especially) can contain passwords, keys and internal paths. Only the given job name and the program name are recorded.

## 2026-10-11: Progress signal details (module 1)

- **Folder progress** means more bytes, more files, or a file written to more recently (a file rewritten in place doesn't change size or count). "Now copying" is the most recently changed file.
- **Folders are only looked at,** never opened or written. A folder that doesn't exist yet counts as empty, because the job may create it. Files or folders that vanish or can't be read mid-count are skipped, not fatal. Symbolic links aren't followed.
- **rclone:** only a rising `stats.bytes` counts. A repeated stats line is not progress. The tracker also notes whether any stats line has been seen, so the watcher can warn if `--use-json-log` was forgotten.
- **Output lines:** a non-blank line counts as progress unless it matches `--ignore-output` (case-insensitive), so heartbeat lines can't hide a stall.

## 2026-10-11: Watcher details (module 2)

- **The job runs without a shell,** exactly as given after `--`. Its output is passed through to the screen. Watcher messages go to stderr with a `[job-watch]` prefix, so the job's own standard output stays clean for scripts.
- **Exit codes:** job-watch exits with the job's own code. 127 means the command couldn't start (the usual "command not found" code). 130 means interrupted (Ctrl-C).
- **Stalls:** "stalled" is sent once per stall; "resumed" is sent when progress returns (with how long it was stalled). If progress returns at the very end, "resumed" is still reported before "finished".
- **Speed and ETA:** speed is the average since the start. The ETA uses it and is given only when a total is known (`--expect-bytes`, or rclone's own total).
- **Status file:** `job-watch-status/<name>.json` holds the latest state. `<name>.history` gets one line per check, so a job's progress can be reviewed afterwards.
- **Tidied after watching a real run:** status lines now use plain `|` separators, because `·` showed as `�` in a Windows terminal. A finished job says "last file …" instead of "now copying …", with no ETA.
- **Tests:** fake jobs with a 1-second stall time. The timing-based tests were run three times in a row to check they're stable: 27/27 each time.
