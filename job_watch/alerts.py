"""Module 3: send events to delivery-ops-hub's webhook, reusing its sender and outbox (imported, not copied).

Sending happens in a background thread, so the watcher never waits on the network. Alerting
can never fail a job: if anything is missing, job-watch says so once and only logs locally.
"""

import importlib
import queue
import sys
import threading
from pathlib import Path


class AlertSender:
    def __init__(self, settings, secret):
        self.enabled, self.reason = False, None
        if settings is None:
            self.reason = "no settings file (copy job-watch.example.toml to job-watch.toml)"
            return
        hub = Path(settings["ops_hub_path"]) if settings["ops_hub_path"] else None
        if not settings["webhook_url"]:
            self.reason = "no webhook_url in the settings"
        elif hub is None or not (hub / "delivery_ops_hub").is_dir():
            self.reason = f"delivery-ops-hub not found at {settings['ops_hub_path']}"
        elif not secret:
            self.reason = "OPS_HUB_WEBHOOK_SECRET is not set"
        if self.reason:
            return

        if str(hub) not in sys.path:
            sys.path.insert(0, str(hub))
        self._post = importlib.import_module("delivery_ops_hub.send").post_json
        self._outbox = importlib.import_module("delivery_ops_hub.outbox")
        self._settings, self._secret = settings, secret
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._work, daemon=True)
        self._thread.start()
        self.enabled = True

    def __call__(self, event):
        if self.enabled:
            self._queue.put(event)

    def close(self, timeout=120):
        """Wait (up to `timeout` seconds) for events still being sent, so none are lost at the end."""
        if self.enabled:
            self._queue.put(None)
            self._thread.join(timeout)

    def _work(self):
        s = self._settings
        while (event := self._queue.get()) is not None:
            result = self._post(s["webhook_url"], event, self._secret, timeout=s["timeout_seconds"],
                                delays=tuple(s["retry_delays"]))
            if result.delivered:
                continue
            if result.status == 502 and (result.reply or {}).get("logged") is True:
                _say(f"{event['event']} was logged by n8n, but its ALERT FAILED: tell the team directly")
                continue
            path = self._outbox.save(s["outbox_dir"], event)
            _say(f"{event['event']} NOT DELIVERED to n8n ({result.error}); saved to {path}. "
                 "Resend later with delivery-ops-hub's 'resend' command.")


def _say(text):
    print(f"[job-watch] {text}", file=sys.stderr, flush=True)
