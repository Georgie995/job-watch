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
