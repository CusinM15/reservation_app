# ─────────────────────────────────────────────────────────────────────────
# tests/test_zasloni.py — Testi digitalnega zaslona (/zasloni)
# ─────────────────────────────────────────────────────────────────────────

import os

os.environ.setdefault("DATABASE_URL", "postgresql://postgres@localhost:5432/testdb")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import School
from app.config import settings
from app.tenancy import default_school_admin_username


def _default_school_id() -> int | None:
    db = SessionLocal()
    try:
        s = db.query(School).filter(School.slug == settings.DEFAULT_SCHOOL_SLUG).first()
        return s.id if s else None
    finally:
        db.close()


def test_zasloni_javen_in_vraca_html():
    with TestClient(app) as c:
        r = c.get("/zasloni")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "fullscreen-mode" in r.text
        assert "fs-header" in r.text


def test_zasloni_status_javen():
    with TestClient(app) as c:
        r = c.get("/zasloni/status")
        assert r.status_code == 200
        assert "AKTIVNI IP-ji" in r.text
        assert "NADOMEŠČANJA" in r.text


def test_zasloni_random_image_json():
    with TestClient(app) as c:
        r = c.get("/zasloni/random_image")
        assert r.status_code == 200
        assert "application/json" in r.headers["content-type"]
        data = r.json()
        assert "slika" in data
        assert data["slika"].startswith(("vec_obvestil/", "obvestila/"))


def test_zasloni_nastavitve_so_v_school_settings():
    from app.tenancy import SCHOOL_SETTING_KEYS, SchoolConfig, env_default_settings
    for k in ("ZASLON_URL", "ZASLON_POKAZI_NADOMESCANJA", "ZASLON_CAS_OBVESTILA",
              "ZASLON_MIN_CAS_TABELE", "ZASLON_HITROST_DRSENJA"):
        assert k in SCHOOL_SETTING_KEYS, f"{k} manjka v SCHOOL_SETTING_KEYS"
        assert k in env_default_settings(), f"{k} manjka v env_default_settings"
    cfg = SchoolConfig(None, {})
    assert cfg.get_str("ZASLON_URL") == "https://urniki.easistent.com/nadomescanja/d960638bb866d19b58f4e2de616db8eb56e73cfe"
    assert cfg.get_int("ZASLON_CAS_OBVESTILA", 0) == 5


def test_school_settings_put_sprejme_bool_in_float():
    from app.tenancy import get_school_settings_map
    with TestClient(app) as c:
        sid = _default_school_id()
        assert sid is not None
        admin_user = default_school_admin_username(settings.DEFAULT_SCHOOL_SLUG)
        login = c.post("/auth/login", data={"username": admin_user, "password": "admin123"})
        assert login.status_code == 200, login.text[:200]
        r = c.put(f"/api/schools/{sid}/settings", json={"values": {
            "ZASLON_POKAZI_NADOMESCANJA": True,
            "ZASLON_CAS_OBVESTILA": "7",
            "ZASLON_MIN_CAS_TABELE": "3",
            "ZASLON_HITROST_DRSENJA": "1.5",
        }})
        assert r.status_code == 200, r.text[:300]
        db = SessionLocal()
        try:
            m = get_school_settings_map(db, sid)
        finally:
            db.close()
        assert m.get("ZASLON_POKAZI_NADOMESCANJA") == "true"
        assert m.get("ZASLON_CAS_OBVESTILA") == "7"
        assert m.get("ZASLON_HITROST_DRSENJA") == "1.5"