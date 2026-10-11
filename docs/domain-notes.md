# Domain notes

Why this tool exists, from Georgi's work. Written generically, with no client, project or product details.

| What happened | What job-watch does about it |
|---|---|
| Long tape restores, tape writes and cloud transfers run as Linux commands for hours. | Runs the job through a watcher and alerts once when it finishes or fails. |
| While a restore runs, you can't see which file is copying, so people list directories "blindly" to guess progress. | A status line and `job-watch status` show files and bytes done, the file being copied now, speed, and the time since the last progress. |
| A tape copy reached a bad section, **stalled**, and later errored out and crashed (F9). | Detects a stall after a set time with no progress (default 10 minutes) and alerts *before* the job dies. It never stops the job. |
| The total size of a tape restore often isn't known until the tape has been indexed. | Gives an ETA only when a total is known (rclone's own total, or one you supply). Otherwise it shows progress and speed without guessing. |
| Cloud transfers used rclone in a terminal. | Reads rclone's documented JSON progress stats, so repeated progress lines don't hide a stall. |
