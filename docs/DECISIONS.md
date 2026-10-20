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

## 2026-10-11: Alerts through delivery-ops-hub (module 3)

- **Reuse, don't copy:** job-watch imports delivery-ops-hub's `post_json` and outbox from the folder named in `job-watch.toml`.
- **Sending runs in a background thread,** so a slow or unreachable n8n never delays stall detection. At the end of a run, job-watch waits (up to 2 minutes) for queued events, so none are lost.
- **When sending fails:** an undeliverable event goes to the outbox with a loud message, and delivery-ops-hub's `resend` delivers it later. "Logged but alert failed" (502) is reported, not retried.
- **Alerting can never fail a job.** With no settings file, no delivery-ops-hub, no webhook address or no secret, job-watch says "alerts are off (reason)" once and logs locally. The job's exit code is always passed back unchanged.
- **Windows convenience:** if `OPS_HUB_WEBHOOK_SECRET` isn't in the current terminal, job-watch reads the value saved for the Windows user. A terminal opened before the secret was saved can't see it, which is what happened in project 2's hands-on run. On Linux, only the environment counts.
- **On the n8n side** (delivery-ops-hub): job events are a separate message kind with their own validation, log file (`job-events.csv`) and cards. `started` is logged only; all other events alert.
- **Proof:** an end-to-end live test runs a made-up stalling restore under job-watch and checks that started → stalled → resumed → finished arrive in the real n8n log, with nothing left in the outbox.

## 2026-10-20: Tests run on GitHub after every push, and every Monday

- **Need:** Georgi asked which automations would genuinely improve the published tools (research in his private notes). This repo had no automatic tests on GitHub, and it is built for Linux but was developed on Windows.
- **Options:** (a) leave as is; (b) test this repo alone; (c) also fetch delivery-ops-hub, whose sender the alert tests reuse.
- **Decision (Georgi, 2026-10-20):** (c), on Linux and Windows, Python 3.11 and 3.13. **Sibling repos (Georgi's choice):** each run fetches the latest delivery-ops-hub next to this repo, so the joined-up tests run on GitHub too, not only on the development PC. A change in a sibling can turn this repo's tests red; that is the point.
  - **Every Monday at 06:00 UTC** the tests run again even if nothing was pushed, so a new Python version or a change in a sibling repo is noticed without anyone looking.
  - **Safety:** read-only permissions, no secrets (so no AI call is possible), and only GitHub's own official actions.
- **Known limits:**
  - GitHub pauses scheduled runs in a repo with no activity for 60 days.
  - **Fake jobs only.** Passing on GitHub's Linux machine is not the pending real Linux run with tape or rclone jobs, and the README says so.
- **Tested by:** before pushing, each suite was run from fresh local clones laid out exactly as the workflow lays them out. A checker confirmed every workflow file follows the rules above, and each rule was broken on purpose once (write permission, no Monday run, a secret, a non-GitHub action, a wrong or missing sibling, the wrong machines); the checker caught every break. The workflow itself can only be fully proven on GitHub, by the first run after pushing.
