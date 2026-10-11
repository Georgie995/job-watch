# Walkthrough

A plain-English explanation of each part, written for someone with no technical background.

---

## Module 1: how the watcher tells whether a job is moving

**In one sentence:** the watcher has three ways of noticing that a long job is still making progress, and it's careful not to be fooled by things that only *look* like progress.

**Like this:** to check a restore is still going, you'd look at the destination folder, see whether new files are appearing, and see which file is newest. The watcher does exactly that, every 30 seconds, without you having to list folders by hand. It has three ways to tell:

1. **The folder grows.** More files, more gigabytes, or a file still being written to. The newest file is shown as "now copying".
2. **rclone's own counter goes up.** rclone (for cloud transfers) regularly prints how much it has transferred. The trap: it keeps printing even when it's stuck. So the watcher only counts it as progress when the **amount transferred actually rises**.
3. **The job prints something new.** Except lines you've marked as "just a heartbeat", like "still running…", which programs print even when stuck.

**It never changes anything:** it only looks at names, sizes and times. If a temporary file disappears while it's counting, or a folder doesn't exist yet, it carries on rather than giving up.

**Tested by:** 13 automatic tests, including the two traps: repeated rclone lines and heartbeat lines must **not** count as progress.

---

## Module 2: the watcher

**In one sentence:** you start a long job *through* the watcher, and it keeps an eye on it, tells you what's happening, and says clearly when the job finishes, fails, stalls or recovers.

**Like this:** imagine asking a colleague to sit next to a restore for you. Every half minute they glance at it and note down how many files are done, how many gigabytes, which file is copying now, and when it last moved. If nothing has moved for 10 minutes, they tell you once: "it's stuck". If it starts moving again, they tell you "it's going again". When it ends, they tell you whether it worked, and if not, what the last error message said. **They never touch the machine.**

What it gives you:
- **A status line on screen**, e.g. `Restore TAPE001: running | 0:42:10 | 1204 files | 812.4 GB | now copying clip_0457.mov | 410 MB/s | last progress 0:00:40 ago | ETA unknown (no total)`.
- **`job-watch status`**, which anyone can type in another terminal to see the same thing. No more listing folders blindly.
- **A record of every event** (started, stalled, resumed, finished, failed, interrupted) in a log.
- **The job's own result** (success or failure code), so anything that runs it still sees the right answer.
- **Never the full command.** Commands can contain passwords, so only the job's name and the program's name are written down.

**Tested by:** tiny fake jobs that copy files, go quiet and come back, fail with "drive not ready", print "still running" while stuck, or imitate rclone repeating the same numbers. In the tests "stuck" means 1 second instead of 10 minutes. 30 tests in total, stable across repeated runs.

---

## Module 3: alerts through the existing alert system

**In one sentence:** when the watcher has something to say (finished, failed, stuck, going again, interrupted), it now sends it to the same alert system as the delivery checks, so the team sees it, and there's a record.

**Like this:** the colleague watching the restore no longer has to come and find you. They post a note in the team's alert channel and write a line in the logbook. If the alert channel is down, they put the note in an in-tray and post it later. If there's no alert channel at all, they still write in their own notebook, and they never stop watching the job because of it.

- **It reuses project 2's "post office":** the same sender, the same secret password and the same in-tray (outbox). Nothing is copied.
- **Sending happens in the background,** so the watcher keeps checking the job while a message is on its way.
- **In n8n** (project 2), job messages get **their own logbook** (`job-events.csv`), so the delivery-check log is unchanged. Each kind of event gets an alert card:
  - **FINISHED: Restore TAPE001** (after 2:14:05, 1,204 files);
  - **FAILED** (exit code and last error lines);
  - **STALLED** (no progress for 10 minutes; nothing was stopped);
  - **RESUMED**;
  - **INTERRUPTED**.

  "Started" is only written in the logbook.
- **Proven end to end:** a made-up restore ran under job-watch, went quiet and recovered. The real n8n logbook received started, stalled, resumed and finished, with nothing stuck in the in-tray. All of project 2's original tests still pass.
