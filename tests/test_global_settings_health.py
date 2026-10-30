# ─────────────────────────────────────────────────────────────────────────
# tests/test_global_settings_health.py — unit testi za _trigger_host_report
# (gumb "Pošlji zdravje/stanje clustra" → Debian trigger webhook).
# Omrežja se tu NE kličejo — urllib.request.urlopen je mockan.
# ─────────────────────────────────────────────────────────────────────────

import os
from unittest.mock import patch

from app.routers.global_settings import _trigger_host_report

# k8s enableServiceLinks injecta legacy varje za Service report-trigger;
# preverimo, da nobeden ne vpliva na URL grading.
_LEGACY_K8S_ENV = ["REPORT_TRIGGER_PORT", "REPORT_TRIGGER_HOST", "REPORT_TRIGGER_SERVICE_HOST"]
_CUSTOM_ENV = ["TRIGGER_WEBHOOK_HOST", "TRIGGER_WEBHOOK_PORT"]


class _FakeResp:
    def __init__(self, status=202):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _strip_env(monkeypatch):
    """Odstrani legacy + custom override varje → čist default URL."""
    for k in _LEGACY_K8S_ENV + _CUSTOM_ENV:
        monkeypatch.delenv(k, raising=False)


def _patch_urlopen(status=202):
    return patch("urllib.request.urlopen", return_value=_FakeResp(status))


def _called_url(mock) -> str:
    return mock.call_args.args[0].full_url


def test_trigger_url_ignores_k8s_legacy_env(monkeypatch):
    """REPORT_TRIGGER_PORT=tcp://IP:PORT (legacy) NE sme pokvariti URL-ja
    (bug 30.10.; fix 0fbadd8 → TRIGGER_WEBHOOK_* + int parse z fallbackom)."""
    monkeypatch.setenv("REPORT_TRIGGER_PORT", "tcp://10.43.25.18:8791")
    monkeypatch.setenv("REPORT_TRIGGER_SERVICE_HOST", "10.43.25.18")
    with _patch_urlopen() as m:
        sent, _ = _trigger_host_report()
    assert sent is True
    assert _called_url(m) == "http://report-trigger.sola-app.svc.cluster.local:8791/"


def test_trigger_default_url(monkeypatch):
    _strip_env(monkeypatch)
    with _patch_urlopen() as m:
        sent, _ = _trigger_host_report()
    assert sent is True
    assert _called_url(m) == "http://report-trigger.sola-app.svc.cluster.local:8791/"


def test_trigger_custom_webhook_overrides(monkeypatch):
    """Ne-k8s override ključa še vedno delujeta."""
    _strip_env(monkeypatch)
    monkeypatch.setenv("TRIGGER_WEBHOOK_PORT", "8792")
    with _patch_urlopen() as m:
        sent, _ = _trigger_host_report()
    assert sent is True
    assert _called_url(m) == "http://report-trigger.sola-app.svc.cluster.local:8792/"


def test_trigger_bad_custom_port_falls_back(monkeypatch):
    """Nenumeričen override porta → fallback na 8791 (ne crash)."""
    _strip_env(monkeypatch)
    monkeypatch.setenv("TRIGGER_WEBHOOK_PORT", "tcp://x:99")
    with _patch_urlopen() as m:
        sent, _ = _trigger_host_report()
    assert sent is True
    assert _called_url(m) == "http://report-trigger.sola-app.svc.cluster.local:8791/"


def test_trigger_non_202_reports_status(monkeypatch):
    _strip_env(monkeypatch)
    with _patch_urlopen(status=500) as m:
        sent, msg = _trigger_host_report()
    assert sent is False
    assert "500" in msg


def test_trigger_connection_failure_reports_message(monkeypatch):
    _strip_env(monkeypatch)
    with patch("urllib.request.urlopen", side_effect=OSError("Name or service not known")):
        sent, msg = _trigger_host_report()
    assert sent is False
    assert "Trigger služba ni dosegljiva" in msg
