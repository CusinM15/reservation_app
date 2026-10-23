# ─────────────────────────────────────────────────────────────────────────
# tests/test_vodstvo_prostori.py — Prostori »samo za vodstvo«
# (PROSTORI_VODSTVO): vidni in rezervabilni samo admin/vodstvo.
# Navaden učitelj zanje sploh ne ve (API jih filtrira).
# ─────────────────────────────────────────────────────────────────────────

from datetime import date, timedelta

from app.database import SessionLocal
from app.models import SchoolSetting
from tests.conftest import login, default_school_id

FUTURE = (date.today() + timedelta(days=7)).isoformat()
H = {"Content-Type": "application/json"}

RESTRICTED = "sef-kabineta"
PUBLIC_ROOM = "racunalnica"
ALL_ROOMS = "racunalnica,ladja,sef-kabineta"


def _set_rooms(client, vodstvo: str = ""):
    """Nastavi PROSTORI + PROSTORI_VODSTVO prek settings API (kot šolski admin)."""
    sid = default_school_id()
    r = client.put(f"/api/schools/{sid}/settings", json={"values": {
        "PROSTORI": ALL_ROOMS,
        "PROSTORI_VODSTVO": vodstvo,
    }})
    assert r.status_code == 200, r.text


def _db_setting(sid: int, key: str) -> str:
    db = SessionLocal()
    try:
        row = db.query(SchoolSetting).filter(
            SchoolSetting.school_id == sid, SchoolSetting.key == key
        ).first()
        return row.value if row else None
    finally:
        db.close()


# ── Shranjevanje ────────────────────────────────────────────────────────

def test_vodstvo_setting_persists(client, make_user):
    admin = make_user("admin")
    login(client, admin.username)
    _set_rooms(client, RESTRICTED)
    sid = default_school_id()
    assert _db_setting(sid, "PROSTORI_VODSTVO") == RESTRICTED


def test_vodstvo_setting_unknown_key_rejected(client, make_user):
    admin = make_user("admin")
    login(client, admin.username)
    sid = default_school_id()
    r = client.put(f"/api/schools/{sid}/settings", json={"values": {
        "PROSTORI_VODSTVO_NEPOZNAN": "x",
    }})
    assert r.status_code == 400


# ── Vidnost (GET /api/prostori) ────────────────────────────────────────

def test_prostori_list_filtered_by_role(client, make_user):
    admin = make_user("admin")
    login(client, admin.username)
    _set_rooms(client, RESTRICTED)

    # Neprijavljen: omejen prostor se sploh ne vidi.
    client.get("/auth/logout")
    r = client.get("/api/prostori")
    assert r.status_code == 200
    assert PUBLIC_ROOM in r.json()
    assert RESTRICTED not in r.json()

    # Učitelj: kot neprijavljen — ne ve zanj.
    teacher = make_user("teacher")
    login(client, teacher.username)
    r = client.get("/api/prostori")
    assert PUBLIC_ROOM in r.json()
    assert RESTRICTED not in r.json()

    # Vodstvo: vidi vse.
    vod = make_user("vodstvo")
    login(client, vod.username)
    r = client.get("/api/prostori")
    assert PUBLIC_ROOM in r.json()
    assert RESTRICTED in r.json()

    # Šolski admin: vidi vse.
    admin2 = make_user("admin")
    login(client, admin2.username)
    r = client.get("/api/prostori")
    assert RESTRICTED in r.json()


def test_prostori_qty_filtered(client, make_user):
    admin = make_user("admin")
    login(client, admin.username)
    # Omejen prostor naj bo tudi »s številom« (kot tablice).
    sid = default_school_id()
    r = client.put(f"/api/schools/{sid}/settings", json={"values": {
        "PROSTORI": ALL_ROOMS,
        "PROSTORI_STEVILO": {PUBLIC_ROOM: "Število tablic", RESTRICTED: "Število tablic"},
        "STEVILA": {"Število tablic": 25},
        "PROSTORI_VODSTVO": RESTRICTED,
    }})
    assert r.status_code == 200, r.text

    teacher = make_user("teacher")
    login(client, teacher.username)
    r = client.get("/api/prostori-qty")
    rooms = r.json()["rooms"]
    assert PUBLIC_ROOM in rooms
    assert RESTRICTED not in rooms

    vod = make_user("vodstvo")
    login(client, vod.username)
    r = client.get("/api/prostori-qty")
    assert RESTRICTED in r.json()["rooms"]


def test_popoldan_prostori_filtered(client, make_user):
    admin = make_user("admin")
    login(client, admin.username)
    sid = default_school_id()
    r = client.put(f"/api/schools/{sid}/settings", json={"values": {
        "PROSTORI": ALL_ROOMS,
        "PROSTORI_POPOLDAN": "ladja," + RESTRICTED,
        "PROSTORI_VODSTVO": RESTRICTED,
    }})
    assert r.status_code == 200, r.text

    teacher = make_user("teacher")
    login(client, teacher.username)
    r = client.get("/api/popoldan")
    assert RESTRICTED not in r.json()["prostori"]
    assert "ladja" in r.json()["prostori"]

    vod = make_user("vodstvo")
    login(client, vod.username)
    r = client.get("/api/popoldan")
    assert RESTRICTED in r.json()["prostori"]


# ── Rezerviranje ───────────────────────────────────────────────────────

def test_teacher_cannot_reserve_restricted_room(client, make_user):
    admin = make_user("admin")
    login(client, admin.username)
    _set_rooms(client, RESTRICTED)

    teacher = make_user("teacher")
    login(client, teacher.username)
    r = client.post("/api/rezervacije", json={
        "date": FUTURE, "hour": 0, "prostor": RESTRICTED, "razred": "5.a", "teacher_id": 999,
    })
    assert r.status_code == 403, r.text


def test_vodstvo_can_reserve_restricted_room(client, make_user):
    admin = make_user("admin")
    login(client, admin.username)
    _set_rooms(client, RESTRICTED)

    vod = make_user("vodstvo")
    login(client, vod.username)
    r = client.post("/api/rezervacije", json={
        "date": FUTURE, "hour": 0, "prostor": RESTRICTED, "razred": "5.a", "teacher_id": 999,
    })
    assert r.status_code == 201, r.text
    assert r.json()["prostor"] == RESTRICTED


# ── Seznam rezervacij ──────────────────────────────────────────────────

def test_rezervacije_list_hides_restricted_for_teacher(client, make_user):
    admin = make_user("admin")
    login(client, admin.username)
    _set_rooms(client, RESTRICTED)

    # Vodstvo naredi rezervacijo v omejenem prostoru.
    vod = make_user("vodstvo")
    login(client, vod.username)
    r = client.post("/api/rezervacije", json={
        "date": FUTURE, "hour": 1, "prostor": RESTRICTED, "razred": "5.a", "teacher_id": 999,
    })
    assert r.status_code == 201, r.text

    # Učitelj te rezervacije ne sme videti.
    teacher = make_user("teacher")
    login(client, teacher.username)
    r = client.get("/api/rezervacije")
    assert r.status_code == 200
    assert all(x["prostor"] != RESTRICTED for x in r.json())

    # Neposredno poizvedovanje po omejenem prostoru → 403.
    r = client.get("/api/rezervacije", params={"prostor": RESTRICTED})
    assert r.status_code == 403

    # Admin vidi vse.
    admin2 = make_user("admin")
    login(client, admin2.username)
    r = client.get("/api/rezervacije")
    assert any(x["prostor"] == RESTRICTED for x in r.json())
