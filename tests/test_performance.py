# ─────────────────────────────────────────────────────────────────────────
# tests/test_performance.py — nastavitve, ki vplivajo na hitrost delovanja
#
# Povod (2026-09-25): aplikacija, gostovana na Railwayu, se uporabniku zdi
# občutno počasnejša od tiste v k3s. Del razlike je v naravi gostovanja
# (oddaljen strežnik + upravljana baza za proxyjem), del pa v nastavitvah
# strežnika. Te teste zapiramo zato, da se te nastavitve ne »izgubijo«:
#   1. gzip stiskanje odgovorov (HTML/JSON) — manj prenosa,
#   2. preverjanje in obnavljanje povezav na bazo (ni čakanja na mrtve povezave),
#   3. nastavljivo število delavcev (WEB_WORKERS) za okolja z več CPU.
# ─────────────────────────────────────────────────────────────────────────

from pathlib import Path

from app.database import engine
from tests.conftest import login


# ── 1. Gzip stiskanje ────────────────────────────────────────────────

def test_large_pages_are_gzipped(client, make_user):
    """Stran s koledarjem se stisne, če brskalnik to podpira."""
    user = make_user()
    login(client, user.username)

    r = client.get("/", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"
    assert len(r.content) > 0


def test_small_responses_are_not_gzipped(client):
    """Majhnih odgovorov (pod pragom 1000 B) ne stiskamo po nepotrebnem."""
    r = client.get("/health", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") is None


# ── 2. Sklad povezav na bazo ─────────────────────────────────────────

def test_engine_checks_dead_connections():
    """Brez tega prva zahteva po mirovanju čaka na ponovno vzpostavitev."""
    pool = engine.pool
    assert getattr(pool, "_pre_ping", False) is True
    assert getattr(pool, "_recycle", 0) and int(pool._recycle) > 0


def test_engine_pool_is_bounded():
    """Sklad mora imeti velikost (ne neomejeno odpiranje povezav)."""
    pool = engine.pool
    assert int(pool.size()) >= 1
    assert int(getattr(pool, "_max_overflow", 0)) >= 0


# ── 3. Nastavljivo število delavcev ──────────────────────────────────

def test_dockerfile_workers_are_configurable():
    """WEB_WORKERS omogoča več delavcev na okolju z več CPU; privzeto 1 (k3s)."""
    text = Path("Dockerfile").read_text(encoding="utf-8")
    assert "${WEB_WORKERS:-1}" in text
    assert "${PORT:-8002}" in text
