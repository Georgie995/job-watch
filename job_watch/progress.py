"""Progress signal 3: new output lines from the job.

Some programs print "still running…" style lines whether or not anything is moving. Those
heartbeat lines can be listed with --ignore-output, so they don't hide a stall.
"""

import re


class OutputTracker:
    def __init__(self, ignore=None):
        self._ignore = re.compile(ignore, re.IGNORECASE) if ignore else None

    def feed(self, line):
        text = line.strip()
        if not text:
            return False
        if self._ignore and self._ignore.search(text):
            return False
        return True
