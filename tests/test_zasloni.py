# ─────────────────────────────────────────────────────────────────────────
# tests/test_zasloni.py — Testi digitalnega zaslona (/zasloni)
# ─────────────────────────────────────────────────────────────────────────

import json
import os

os.environ.setdefault("DATABASE_URL", "postgresql://postgres@localhost:5432/testdb")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import School
from app.config import settings
from app.tenancy import default_school_admin_username
from tests.conftest import login


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


def test_per_sola_alias_zasloni_javen():
    """Vsaka šola dobi svojo kratko /nadomescanja_<slug> pot, javno brez prijave."""
    from app.tenancy import ALIAS_KINDS, _ALIAS_RE, generate_aliases
    assert ALIAS_KINDS.get("nadomescanja") == "/zasloni"
    assert _ALIAS_RE.match("nadomescanja_ostcj") is not None
    pairs = generate_aliases(settings.DEFAULT_SCHOOL_SLUG)
    alias = next((a for a, k in pairs if k == "nadomescanja" and "_" in a), None)
    assert alias, f"manjka generirani nadomescanja_<slug>: {dict(pairs)}"
    with TestClient(app) as c:
        r = c.get(f"/{alias}", follow_redirects=False)
        assert r.status_code == 200, f"/{alias} → {r.status_code}"
        assert "text/html" in r.headers["content-type"]
        assert "fullscreen-mode" in r.text


def test_goli_slug_zasloni_javen():
    """Goli slug šole (npr. /ostcj) → /zasloni, javno brez prijave."""
    from app.tenancy import generate_aliases
    pairs = generate_aliases(settings.DEFAULT_SCHOOL_SLUG)
    bare = next((a for a, k in pairs if k == "nadomescanja" and "_" not in a), None)
    assert bare, f"manjka goli slug (brez predpone) v generate_aliases: {dict(pairs)}"
    with TestClient(app) as c:
        r = c.get(f"/{bare}", follow_redirects=False)
        assert r.status_code == 200, f"/{bare} → {r.status_code}"
        assert "text/html" in r.headers["content-type"]
        assert "fullscreen-mode" in r.text


def test_zasloni_obvestila_vrni_urejen_seznam():
    """/zasloni/obvestila vrne seznam aktivnih obvestil po vrsti (JSON)."""
    with TestClient(app) as c:
        r = c.get("/zasloni/obvestila")
        assert r.status_code == 200
        assert "application/json" in r.headers["content-type"]
        data = r.json()
        assert "obvestila" in data
        assert isinstance(data["obvestila"], list)
        for u in data["obvestila"]:
            assert isinstance(u, dict)
            assert u["type"] in ("image", "text")
            if u["type"] == "image":
                assert isinstance(u.get("src"), str)
                assert u["src"].startswith(("vec_obvestil/", "obvestila/"))
            else:
                assert isinstance(u.get("text"), str)


def test_zasloni_obvestila_vrni_tekst_in_slike(client, make_user):
    """/zasloni/obvestila vrne tudi tekstovna obvestila (iz ZASLON_OBVESTILA_TEKST),
    zaporedena za slikovnimi, v rotacijskem vrstnem redu."""
    from app.tenancy import SCHOOL_SETTING_KEYS, env_default_settings
    assert "ZASLON_OBVESTILA_TEKST" in SCHOOL_SETTING_KEYS
    assert "ZASLON_OBVESTILA_TEKST" in env_default_settings()

    admin = make_user(role="admin")
    login(client, admin.username)
    sid = _default_school_id()

    r = client.put(f"/api/schools/{sid}/settings", json={
        "values": {"ZASLON_OBVESTILA_TEKST": json.dumps(["Prvo obvestilo", "Drugo obvestilo"], ensure_ascii=False)}
    })
    assert r.status_code == 200, r.text

    resp = client.get("/zasloni/obvestila")
    assert resp.status_code == 200
    data = resp.json()
    texts = [x["text"] for x in data["obvestila"] if x["type"] == "text"]
    assert "Prvo obvestilo" in texts
    assert "Drugo obvestilo" in texts
    # Tekstovna pridejo PO slikovnih (če obstajajo slike).
    imgs = [x for x in data["obvestila"] if x["type"] == "image"]
    if imgs:
        idx_first_img = data["obvestila"].index(imgs[0])
        first_text_i = next(i for i, x in enumerate(data["obvestila"]) if x["type"] == "text")
        assert idx_first_img < first_text_i


def test_zasloni_obvestila_tekst_najvec_5(client, make_user):
    """Strežnik zavrne 400, če bi šola shranila več kot 5 tekstovnih obvestil."""
    admin = make_user(role="admin")
    login(client, admin.username)
    sid = _default_school_id()

    r = client.put(f"/api/schools/{sid}/settings", json={
        "values": {"ZASLON_OBVESTILA_TEKST": json.dumps(["1", "2", "3", "4", "5", "6"])}
    })
    assert r.status_code == 400, r.text
    assert "5" in r.text


def test_zasloni_obvestila_nastavitev_je_v_kljucih():
    """ZASLON_OBVESTILA je registriran v school settings (ključ + default)."""
    from app.tenancy import SCHOOL_SETTING_KEYS, env_default_settings
    assert "ZASLON_OBVESTILA" in SCHOOL_SETTING_KEYS
    assert "ZASLON_OBVESTILA" in env_default_settings()