"""Module 3 tests: sending events through delivery-ops-hub's sender (reused by import, not copied).

Uses a small web server inside the test, on this PC only. A final test runs end to end against
the real n8n if it's running.
"""

import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from job_watch import cli

ROOT = Path(__file__).resolve().parents[1]
OPS_HUB = ROOT.parent / "delivery-ops-hub"
JOBS = str(Path(__file__).with_name("jobs.py"))
SECRET = "test-secret-1234567890"

pytestmark = pytest.mark.skipif(not (OPS_HUB / "delivery_ops_hub").exists(),
                                reason="delivery-ops-hub repo not found next to job-watch")


@pytest.fixture
def server():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append({"headers": dict(self.headers), "json": body})
            data = json.dumps({"logged": True, "alerted": body["event"] != "started"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/webhook/delivery-check", received
    httpd.shutdown()
    httpd.server_close()


def closed_url():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"http://127.0.0.1:{port}/webhook/delivery-check"


def config(tmp_path, url, ops_hub=OPS_HUB):
    path = tmp_path / "job-watch.toml"
    path.write_text(f'ops_hub_path = "{Path(ops_hub).as_posix()}"\nwebhook_url = "{url}"\n'
                    f'outbox_dir = "{(tmp_path / "outbox").as_posix()}"\nretry_delays = []\n', encoding="utf-8")
    return path


def run(tmp_path, cfg, *job, extra=()):
    return cli.main(["run", "--name", "Restore TAPE001", "--config", str(cfg), "--check-seconds", "0.2",
                     "--status-dir", str(tmp_path / "status"), "--log-dir", str(tmp_path / "logs"), *extra,
                     "--", sys.executable, JOBS, *[str(a) for a in job]])


def test_events_are_sent_with_the_secret_and_never_the_command(tmp_path, server, monkeypatch):
    url, received = server
    monkeypatch.setenv("OPS_HUB_WEBHOOK_SECRET", SECRET)
    code = run(tmp_path, config(tmp_path, url), "copy", tmp_path / "d", 2, 0.01, "--password=SUPERSECRET123")
    assert code == 0
    assert [r["json"]["event"] for r in received] == ["started", "finished"]
    assert all(r["headers"]["X-Ops-Hub-Key"] == SECRET for r in received)
    assert all(r["json"]["kind"] == "job_event" for r in received)
    assert "SUPERSECRET123" not in json.dumps([r["json"] for r in received])


def test_unreachable_n8n_puts_events_in_the_outbox_and_the_job_result_is_unchanged(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPS_HUB_WEBHOOK_SECRET", SECRET)
    code = run(tmp_path, config(tmp_path, closed_url()), "fail")
    assert code == 3                                                   # still the job's own exit code
    saved = sorted((tmp_path / "outbox").glob("*.json"))
    assert sorted(json.loads(p.read_text(encoding="utf-8"))["event"] for p in saved) == ["failed", "started"]
    assert "NOT DELIVERED" in capsys.readouterr().err


def test_missing_secret_means_log_only_and_the_job_still_runs(tmp_path, server, monkeypatch, capsys):
    url, received = server
    monkeypatch.delenv("OPS_HUB_WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr(cli, "_saved_user_secret", lambda: "")
    assert run(tmp_path, config(tmp_path, url), "copy", tmp_path / "d", 1, 0.01) == 0
    assert received == []
    assert "alerts are off" in capsys.readouterr().err
    assert list((tmp_path / "logs").glob("*.jsonl"))                   # still logged locally


def test_missing_delivery_ops_hub_means_log_only(tmp_path, server, monkeypatch, capsys):
    url, received = server
    monkeypatch.setenv("OPS_HUB_WEBHOOK_SECRET", SECRET)
    assert run(tmp_path, config(tmp_path, url, ops_hub=tmp_path / "nowhere"), "copy", tmp_path / "d", 1, 0.01) == 0
    assert received == []
    assert "alerts are off" in capsys.readouterr().err


def test_no_alerts_flag_sends_nothing(tmp_path, server, monkeypatch):
    url, received = server
    monkeypatch.setenv("OPS_HUB_WEBHOOK_SECRET", SECRET)
    run(tmp_path, config(tmp_path, url), "copy", tmp_path / "d", 1, 0.01, extra=["--no-alerts"])
    assert received == []


def test_no_settings_file_means_log_only(tmp_path, capsys):
    assert run(tmp_path, tmp_path / "missing.toml", "copy", tmp_path / "d", 1, 0.01) == 0
    assert "alerts are off" in capsys.readouterr().err


# --- End to end against the real n8n (skipped if it isn't running) -----------------------------------

def _n8n_ready():
    import urllib.error
    import urllib.request
    try:
        urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:5678/webhook/delivery-check", data=b"{}",
                                                      method="POST"), timeout=2)
    except urllib.error.HTTPError as error:
        return error.code == 403
    except OSError:
        return False
    return False


@pytest.mark.skipif(not _n8n_ready() or not cli._saved_user_secret(), reason="n8n not running or no saved secret")
def test_end_to_end_a_stall_reaches_the_real_n8n_log_and_alert_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("OPS_HUB_WEBHOOK_SECRET", cli._saved_user_secret())
    job_log = OPS_HUB / "runtime" / "logs" / "job-events.csv"
    before = job_log.read_text(encoding="utf-8-sig").splitlines() if job_log.exists() else []
    cfg = config(tmp_path, "http://localhost:5678/webhook/delivery-check")
    code = cli.main(["run", "--name", "E2E test job", "--config", str(cfg), "--check-seconds", "0.2",
                     "--stall-minutes", str(1 / 60), "--watch", str(tmp_path / "d"),
                     "--status-dir", str(tmp_path / "status"), "--log-dir", str(tmp_path / "logs"),
                     "--", sys.executable, JOBS, "pause", str(tmp_path / "d"), "2.5"])
    assert code == 0
    new_rows = job_log.read_text(encoding="utf-8-sig").splitlines()[len(before):]
    events = [row.split(",")[4] for row in new_rows if "E2E test job" in row]
    assert events == ["started", "stalled", "resumed", "finished"]
    assert not list((tmp_path / "outbox").glob("*.json"))              # everything was delivered
