#!/usr/bin/env python3
"""
report-trigger-server.py — majhen webhook na Debianu (127.0.0.1:8790).

Ob HTTP POST / iz ozadja požene host-mode status report:
    python3 scripts/cluster_report.py --mode host
(tako prispe do GitHub pusha prek SSH ključa, ki ga token nima v podu).

Dosegljiv je SAMO prek reverznega SSH tunela od node-1 (obe strani loopback,
nič javne izpostavitve) → k8s DaemonSet socat proxy → ClusterIP Service.

Usage:
    python3 report-trigger-server.py            # strežnik, privzet 127.0.0.1:8790
"""

import http.server
import json
import logging
import os
import subprocess
import sys
import threading

HOST = os.environ.get("TRIGGER_HOST", "127.0.0.1")
PORT = int(os.environ.get("TRIGGER_PORT", "8790"))
# Sama skripta v repo (absolutno; repo je ~/forgejo/zaslužek/reservation_app_sell)
REPO = os.environ.get("REPORT_REPO", "/home/matej/forgejo/zaslužek/reservation_app_sell")
LOG = "/tmp/report-trigger.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("trigger")


def run_host_report() -> None:
    """Odženi cluster_report.py --mode host v ozadju; ne blokira HTTP."""
    def _run():
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/cluster_report.py", "--mode", "host"],
                cwd=REPO,
                capture_output=True,
                text=True,
                timeout=600,
            )
            tail = (proc.stdout or "")[-500:] + "\n--- STDERR ---\n" + (proc.stderr or "")[-500:]
            log.info("exit=%s | %s", proc.returncode, tail)
        except Exception as exc:  # pragma: no cover
            log.error("napaka pri zagonu skripte: %s", exc)

    threading.Thread(target=_run, daemon=True).start()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        if self.path != "/":
            self.send_response(404)
            self.end_headers()
            return
        run_host_report()
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        body = json.dumps({"accepted": True, "run": "host"})
        self.wfile.write(body.encode())

    def do_GET(self):  # noqa: N802  (healthcheck)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode())

    def log_message(self, format, *args):  # noqa: A002  (tišji dnevnik)
        log.info("req: %s", format % args)


def main() -> None:
    srv = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    log.info("trigger strežnik posluša na %s:%s (repo=%s)", HOST, PORT, REPO)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()