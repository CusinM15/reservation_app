# ─────────────────────────────────────────────────────────────────────────
# tests/test_cluster_report.py — unit testi za scripts/cluster_report.py
# (čiste format funkcije; omrežja/SSH/API se tu ne kličejo).
# ─────────────────────────────────────────────────────────────────────────

import datetime as dt

import pytest

from scripts import cluster_report as cr


# ── uptime_short ────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("1 week, 3 days, 22 hours, 14 minutes", "1t 3d"),
    ("1 week, 1 hour, 13 minutes", "1t"),
    ("4 days, 18 hours, 51 minutes", "4d 18h"),
    ("3 days, 2 hours, 5 minutes", "3d 2h"),
    ("2 hours, 30 minutes", "2h 30m"),
    ("45 minutes", "45m"),
    ("", "0m"),
])
def test_uptime_short(raw, expected):
    assert cr.uptime_short(raw) == expected


# ── boot_short ───────────────────────────────────────────────────────────

def test_boot_short_full_timestamp():
    assert cr.boot_short("2026-10-18 15:33") == "boot 18.10."


def test_boot_short_bad_input_does_not_crash():
    assert cr.boot_short("garbage") == "boot garbage"


# ── age_human ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("delta,expected", [
    (dt.timedelta(days=6), "6d"),
    (dt.timedelta(hours=8), "8h"),
    (dt.timedelta(hours=8, minutes=51), "8h51m"),
    (dt.timedelta(hours=2), "2h"),
    (dt.timedelta(minutes=35), "35m"),
    (dt.timedelta(seconds=20), "0m"),
])
def test_age_human(delta, expected):
    ts = (cr.NOW - delta).strftime("%Y-%m-%d %H:%M:%S")
    assert cr.age_human(ts) == expected


def test_age_human_invalid_input():
    assert cr.age_human("ni-datum") == "?"


# ── pct / load1dec ──────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("36.9231", "37"),
    ("0.0", "0"),
    ("13", "13"),
])
def test_pct(raw, expected):
    assert cr.pct(raw) == expected


def test_pct_none_returns_str():
    assert cr.pct(None) == "None"


@pytest.mark.parametrize("raw,expected", [
    ("1.86", "1.9"),
    ("0.25", "0.2"),
    ("2", "2.0"),
])
def test_load1dec(raw, expected):
    assert cr.load1dec(raw) == expected


# ── short_pod ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("sola-app-66f8c9d89b-abcde", "sola-app"),
    ("cloudflared-7c8d9f0a12-x1y2z", "cloudflared"),
    ("csi-attacher-66f8c9d89b-abcde", "csi-attacher"),
    ("sola-db-1", "sola-db-1"),
    ("sola-db-full-1", "sola-db-full-1"),
    ("engine-image-39d54b3d", "engine-image"),
])
def test_short_pod(raw, expected):
    assert cr.short_pod(raw) == expected


def test_short_pod_keeps_short_suffix():
    # številčni replika suffix (kratek) se ohrani
    assert cr.short_pod("sola-db-1") == "sola-db-1"


# ── age_sec ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("6d", 6 * 86400),
    ("8h51m", 8 * 3600 + 51 * 60),
    ("2h", 7200),
    ("35m", 2100),
    ("?", 0),
])
def test_age_sec(raw, expected):
    assert cr.age_sec(raw) == expected


def test_age_sec_empty():
    assert cr.age_sec("") == 0
