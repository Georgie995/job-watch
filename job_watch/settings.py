"""Settings from job-watch.toml (git-ignored; see job-watch.example.toml).

The webhook secret is never a setting: it comes from the environment variable
OPS_HUB_WEBHOOK_SECRET, the same one delivery-ops-hub uses.
"""

import tomllib
from pathlib import Path

DEFAULTS = {
    "ops_hub_path": None,           # folder of the delivery-ops-hub repo (its sender is reused)
    "webhook_url": None,            # e.g. http://localhost:5678/webhook/delivery-check
    "outbox_dir": "job-watch-outbox",
    "timeout_seconds": 10,
    "retry_delays": [2, 4],         # seconds between attempts (3 attempts), as in delivery-ops-hub
}


class SettingsError(Exception):
    """The settings file is wrong (job-watch stops before running the job)."""


def load_settings(path):
    path = Path(path)
    if not path.exists():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise SettingsError(f"{path} is not valid TOML: {error}") from error
    unknown = set(data) - set(DEFAULTS)
    if unknown:
        raise SettingsError(f"{path}: unknown setting(s): {', '.join(sorted(unknown))}")
    return {**DEFAULTS, **data}
