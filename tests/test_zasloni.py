# ─────────────────────────────────────────────────────────────────────────
# tests/test_zasloni.py — Testi digitalnega zaslona (nadomeščanja)
#
# PRAVILA (od 2026-11-03, posodobljeno za obnovitev obvestil+osveži):
#  - Javna stran nadomeščanj je dostopna LE prek per-šola poti
#    /nadomescanja_<kratica> (middleware jo prepiše na /zasloni).
#  - Gola /zasloni je 404; /zasloni/status in /zasloni/random_image (po
#    refaktorju) ostajata 404, ker nista več v uporabi.
#  - Obvestila + osveži so VRJENI: /zasloni/obvestila, /zasloni/osvezi_at
#    in /zasloni/media/{ime} delujejo (serviranje slik iz DB zasloni_files);
#    zaslon spet rotira slike/tekst in polla osvezi_at.
#  - Admin API za nalaganje/brisanje obvestil (/api/schools/{id}/zasloni/...)
#    ostane (shranjevanje v bazo).
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

# Javna stran nadomeščanj = per-šola alias; gola /zasloni je odstranjena.
ZASLON_POT = f"/nadomescanja_{settings.DEFAULT_SCHOOL_SLUG}"

ODSTRANJENE_POTI = [
    "/zasloni",
    "/zasloni/status",
    "/zasloni/random_image",
]


def _default_school_id() -> int | None:
    db = SessionLocal()
    try:
        s = db.query(School).filter(School.slug == settings.DEFAULT_SCHOOL_SLUG).first()
        return s.id if s else None
    finally:
        db.close()


def _ustvari_solo(slug: str, ime: str):
    """Ustvari (ali prečisti in ponovno ustvari) šolo — vzorec test_govorilne."""
    from app.tenancy import create_school
    from app.models import SchoolSetting
    db = SessionLocal()
    try:
        old = db.query(School).filter(School.slug == slug).first()
        if old:
            db.query(SchoolSetting).filter(
                SchoolSetting.school_id == old.id,
            ).delete(synchronize_session=False)
            db.query(School).filter(School.id == old.id).delete(synchronize_session=False)
        db.commit()
        create_school(db, ime, slug=slug)
        db.commit()
        return db.query(School).filter(School.slug == slug).first().id
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════
# 1. Dostop: vedno prek /nadomescanja_<kratica>; gola /zasloni → 404
# ═══════════════════════════════════════════════════════════════════════

def test_zasloni_gola_in_vse_poti_odstranjene():
    """Gola /zasloni in VSE /zasloni/* poti → 404; deluje le /nadomescanja_<kratica>."""
    with TestClient(app) as c:
        for pot in ODSTRANJENE_POTI:
            r = c.get(pot)
            assert r.status_code == 404, f"{pot} → {r.status_code}"
        r = c.get(ZASLON_POT)
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "fullscreen-mode" in r.text
        assert "fs-header" in r.text


def test_zasloni_stran_vkljuci_obvestila_in_osvezi():
    """Zaslon v HTML-ju vključi rotacijo obvestil (/zasloni/obvestila, /zasloni/media/) in polling osveži_at."""
    with TestClient(app) as c:
        r = c.get(ZASLON_POT)
        assert r.status_code == 200
        assert "/zasloni/obvestila" in r.text
        assert "/zasloni/osvezi_at" in r.text
        assert "/zasloni/media/" in r.text
        assert "preveriOsvezi" in r.text
        assert "obvestiloImg" in r.text
        assert "updateTime" in r.text


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
        assert "fullscreen-mode" in r.text


def test_per_sola_school_name_v_naslovu():
    """/nadomescanja_<slug> pokaže ime TE šole, ne hardkodirane OŠ Toneta Čufarja."""
    _ustvari_solo("zgled", "OŠ Zgled")
    with TestClient(app) as c:
        r = c.get("/nadomescanja_zgled")
        assert r.status_code == 200
        assert "OŠ Zgled" in r.text
        assert "Toneta Čufarja" not in r.text
    # Svež client (brez school_ctx piškotka) → privzeta šola pokaže SVOJE ime.
    with TestClient(app) as c2:
        r2 = c2.get(ZASLON_POT)
        assert r2.status_code == 200
        assert settings.SCHOOL_NAME in r2.text


def test_zasloni_odprt_zaprt_toggle(client, make_user):
    """ZASLON_OMOGOCEN: privzeto odprt; ko admin izklopi → 'trenutno zaprta'."""
    with TestClient(app) as c:
        r = c.get(ZASLON_POT)
        assert r.status_code == 200
        assert "fullscreen-mode" in r.text
        assert "trenutno zaprta" not in r.text

    admin = make_user(role="admin")
    login(client, admin.username)
    sid = _default_school_id()
    r = client.put(f"/api/schools/{sid}/settings", json={"values": {"ZASLON_OMOGOCEN": False}})
    assert r.status_code == 200, r.text

    with TestClient(app) as c:
        r = c.get(ZASLON_POT)
        assert r.status_code == 200
        assert "Nadomeščanja so trenutno zaprta" in r.text
        assert "fullscreen-mode" not in r.text


# ═══════════════════════════════════════════════════════════════════════
# 2. Vsebina zaslona (server-side): tabela ali sporočilo + ura
# ═══════════════════════════════════════════════════════════════════════

def test_zasloni_brez_tabele_pokaze_sporocilo():
    """Brez tabele (testno okolje: eAsistent ni dosegljiv) → 'Danes ni nadomeščanj'."""
    with TestClient(app) as c:
        r = c.get(ZASLON_POT)
        assert r.status_code == 200
        if "Danes ni nadomeščanj" in r.text:
            assert "table-view" not in r.text
        else:
            assert "table-view" in r.text  # če je tabela na voljo, se pokaže


def test_zasloni_time_zone_v_strani():
    """Zaslon vključi časovni pas (Europe/Ljubljana) v JS ure."""
    from app.tenancy import SCHOOL_SETTING_FIELDS, SCHOOL_SETTING_KEYS, env_default_settings
    assert "ZASLON_TIME_ZONE" in SCHOOL_SETTING_KEYS
    assert "ZASLON_TIME_ZONE" in env_default_settings()
    assert env_default_settings()["ZASLON_TIME_ZONE"] == "Europe/Ljubljana"
    labels = {f["key"] for f in SCHOOL_SETTING_FIELDS}
    assert "ZASLON_TIME_ZONE" in labels
    with TestClient(app) as c:
        r = c.get(ZASLON_POT)
        assert r.status_code == 200
        assert "CASOVNI_PAS" in r.text
        assert "Europe/Ljubljana" in r.text


def test_zasloni_time_zone_validacija(client, make_user):
    """Napačen časovni pas → 400; veljaven → shranjen."""
    admin = make_user(role="admin")
    login(client, admin.username)
    sid = _default_school_id()
    assert sid is not None

    r = client.put(f"/api/schools/{sid}/settings", json={
        "values": {"ZASLON_TIME_ZONE": "Napačen/Pas"}
    })
    assert r.status_code == 400, r.text

    r = client.put(f"/api/schools/{sid}/settings", json={
        "values": {"ZASLON_TIME_ZONE": "Europe/Ljubljana"}
    })
    assert r.status_code == 200, r.text


# ═══════════════════════════════════════════════════════════════════════
# 3. Nastavitve (ključi, privzete vrednosti, PUT sprejme bool/float)
# ═══════════════════════════════════════════════════════════════════════

def test_zasloni_nastavitve_so_v_school_settings():
    from app.tenancy import SCHOOL_SETTING_KEYS, SchoolConfig, env_default_settings
    for k in ("ZASLON_URL", "ZASLON_POKAZI_NADOMESCANJA", "ZASLON_CAS_OBVESTILA",
              "ZASLON_MIN_CAS_TABELE", "ZASLON_HITROST_DRSENJA", "ZASLON_TIME_ZONE",
              "ZASLON_OMOGOCEN", "ZASLON_OBVESTILA", "ZASLON_OBVESTILA_TEKST",
              "ZASLON_OSVEZI_AT"):
        assert k in SCHOOL_SETTING_KEYS, f"{k} manjka v SCHOOL_SETTING_KEYS"
        assert k in env_default_settings(), f"{k} manjka v env_default_settings"
    cfg = SchoolConfig(None, {})
    assert cfg.get_str("ZASLON_URL") == "https://urniki.easistent.com/nadomescanja/d960638bb866d19b58f4e2de616db8eb56e73cfe"
    assert cfg.get_int("ZASLON_CAS_OBVESTILA", 0) == 5
    assert cfg.get_str("ZASLON_TIME_ZONE", "") == "Europe/Ljubljana"


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


# ═══════════════════════════════════════════════════════════════════════
# 4. Admin API za nalaganje/brisanje ostane; javne /zasloni/* poti so 404
# ═══════════════════════════════════════════════════════════════════════

def _tiny_png() -> bytes:
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (60, 30), (200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


def test_zasloni_admin_upload_delete_api_dela(client, make_user):
    """Nalaganje/brisanje prek /api/schools/{id}/zasloni/... še dela; javnih poti ni."""
    admin = make_user(role="admin")
    login(client, admin.username)
    sid = _default_school_id()
    assert sid is not None

    png = _tiny_png()
    r = client.post(
        f"/api/schools/{sid}/zasloni/upload",
        files={"file": ("moje_obvestilo.png", png, "image/png")},
    )
    assert r.status_code == 200, r.text
    fname = r.json()["filename"]
    assert fname == "moje_obvestilo.png"

    # naloženo obvestilo je javno dostopno prek /zasloni/media (servirano iz DB)
    with TestClient(app) as c:
        r = c.get(f"/zasloni/media/vec_obvestil/{fname}")
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("image/")

    r = client.post(f"/api/schools/{sid}/zasloni/delete", json={"filename": fname})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/schools/{sid}/zasloni/delete", json={"filename": fname})
    assert r.status_code == 404, r.text


def test_zasloni_admin_osvezi_gumb_dela(client, make_user):
    """Gumb »Osveži vse naprave« (admin API) še deluje."""
    admin = make_user(role="admin")
    login(client, admin.username)
    sid = _default_school_id()
    assert sid is not None
    r = client.post(f"/api/schools/{sid}/zasloni/osvezi")
    assert r.status_code == 200, r.text


def test_zasloni_upload_zavrne_neveljavno(client, make_user):
    """Napačna končnica ali ponarejena vsebina → 400."""
    admin = make_user(role="admin")
    login(client, admin.username)
    sid = _default_school_id()
    assert sid is not None

    r = client.post(
        f"/api/schools/{sid}/zasloni/upload",
        files={"file": ("skripta.txt", b"echo hi", "text/plain")},
    )
    assert r.status_code == 400, r.text

    r = client.post(
        f"/api/schools/{sid}/zasloni/upload",
        files={"file": ("lazni.png", b"to ni png", "image/png")},
    )
    assert r.status_code == 400, r.text


# ═══════════════════════════════════════════════════════════════════════
# 5. Parsanje tabele iz eAsistenta (server-side)
# ═══════════════════════════════════════════════════════════════════════

def test_izrezi_tabelo_iz_ajax_data():
    """eAsistent (10/2026) tabelo naloži prek AJAX /seznam → JSON {data}; ta data
    mora _izrezi_prvo_tabelo sparsati v tabelo, tudi ko inicialni HTML tabele nima."""
    from app.routers.zasloni import _izrezi_prvo_tabelo
    ajax_data = (
        '<div class="card"><div class=card-title>Nadomeščanja po razredih</div>\r\n'
        '<div class=card-content>\r\n'
        '<table class="table_list"><thead><tr>\r\n'
        '<th>Razred</th><th>Ura</th><th>Nadomešča</th>'
        '<th>Učilnica</th><th width="42%">Opombe</th>\r\n'
        "</tr></thead>\r\n"
        '<tr class="not-clickable rowspan border">'
        '<td rowspan="3" class="no-hover">1. A</td>'
        "<td>2b.</td><td><strong>Đuretić Arijana</strong>, MAT</td>"
        "<td>u_1a</td><td>/</td></tr>\r\n"
        "</table>\r\n</div></div>"
    )
    out = _izrezi_prvo_tabelo(ajax_data)
    assert out is not None
    assert "<th>Razred</th>" in out
    assert "table_list" in out
    assert "Đuretić" in out


def test_tabela_iz_ajax_brez_nadomescanj_vrne_none():
    """eAsistent vrne 'Za ta dan ni nadomeščanj.' (data brez <table>) → None, ne
    prazna tabela."""
    from app.routers.zasloni import _tabela_iz_ajax
    class Resp:
        def raise_for_status(self):
            return None
        def json(self):
            return {"data": "        Za ta dan ni nadomeščanj."}
    import unittest.mock as mock
    with mock.patch("requests.get", return_value=Resp()):
        assert _tabela_iz_ajax("https://urniki.easistent.com/nadomescanja/hash", "Europe/Ljubljana") is None