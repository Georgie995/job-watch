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
