"""Testi za rezervacije: ustvarjanje, kapaciteta, ekskluzivnost, brisanje, varnost."""
import pytest
from conftest import create_user, login, make_client, get_user_id

DATE = "2026-09-07"  # ponedeljek


def rez_data(hour=0, prostor="tablice", qty=None, tid=None, razred=None):
    d = {"date": DATE, "hour": hour, "prostor": prostor, "teacher_id": tid}
    if qty is not None:
        d["qty"] = qty
    if razred:
        d["razred"] = razred
    return d


def make_teacher(app_ready):
    """Ustvari učitelja in vrne (client prijavljen kot učitelj, user_id)."""
    c = make_client()
    uname = create_user(c)   # notranja admin prijava + ustvarjanje
    c.get("/auth/logout")    # odjava admina
    login(c, uname)          # prijava kot učitelj
    return c, get_user_id(uname)


# ═══ USTVARJANJE ═══
def test_create_tablice_reservation(app_ready):
    c, uid = make_teacher(app_ready)
    r = c.post("/api/rezervacije", json=rez_data(qty=10, tid=uid))
    assert r.status_code == 201
    assert r.json()["prostor"] == "tablice"
    assert r.json()["qty"] == 10


def test_create_racunalnica_reservation(app_ready):
    c, uid = make_teacher(app_ready)
    r = c.post("/api/rezervacije", json=rez_data(hour=1, prostor="racunalnica", tid=uid))
    assert r.status_code == 201


def test_create_tablice_without_qty_rejected(app_ready):
    c, uid = make_teacher(app_ready)
    r = c.post("/api/rezervacije", json=rez_data(tid=uid))
    assert r.status_code == 400
    assert "qty" in r.json()["detail"].lower()


def test_create_tablice_over_capacity(app_ready):
    c, uid = make_teacher(app_ready)
    assert c.post("/api/rezervacije", json=rez_data(qty=25, tid=uid)).status_code == 201
    r = c.post("/api/rezervacije", json=rez_data(qty=10, tid=uid))  # 25+10=35 > 28
    assert r.status_code == 400
    assert "kapaciteto" in r.json()["detail"]


def test_create_tablice_capacity_boundary(app_ready):
    c, uid = make_teacher(app_ready)
    assert c.post("/api/rezervacije", json=rez_data(qty=25, tid=uid)).status_code == 201
    r = c.post("/api/rezervacije", json=rez_data(qty=3, tid=uid))  # 25+3=28 = max
    assert r.status_code == 201


def test_exclusive_room_conflict(app_ready):
    c, uid = make_teacher(app_ready)
    assert c.post("/api/rezervacije", json=rez_data(hour=2, prostor="racunalnica", tid=uid)).status_code == 201
    r = c.post("/api/rezervacije", json=rez_data(hour=2, prostor="racunalnica", tid=uid))
    assert r.status_code == 400
    assert "zaseden" in r.json()["detail"]


def test_invalid_prostor(app_ready):
    c, uid = make_teacher(app_ready)
    r = c.post("/api/rezervacije", json=rez_data(prostor="bazen", tid=uid))
    assert r.status_code == 400


def test_invalid_hour(app_ready):
    c, uid = make_teacher(app_ready)
    r = c.post("/api/rezervacije", json=rez_data(hour=9, prostor="ladja", tid=uid))
    assert r.status_code == 422


def test_tablice_multiple_teachers_same_slot(app_ready):
    """Tablice niso ekskluzivne — dva učitelja v isti uri (do kapacitete)."""
    c1, uid1 = make_teacher(app_ready)
    c2, uid2 = make_teacher(app_ready)
    assert c1.post("/api/rezervacije", json=rez_data(qty=10, tid=uid1)).status_code == 201
    assert c2.post("/api/rezervacije", json=rez_data(qty=10, tid=uid2)).status_code == 201


# ═══ SEZNAM ═══
def test_list_reservations(app_ready):
    c, uid = make_teacher(app_ready)
    c.post("/api/rezervacije", json=rez_data(qty=10, tid=uid))
    r = c.get("/api/rezervacije")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_list_filter_by_date(app_ready):
    c, uid = make_teacher(app_ready)
    c.post("/api/rezervacije", json=rez_data(qty=10, tid=uid))
    r = c.get(f"/api/rezervacije?date={DATE}")
    assert len(r.json()) == 1
    r = c.get("/api/rezervacije?date=2026-10-01")
    assert len(r.json()) == 0


# ═══ BRISANJE ═══
def test_delete_own_reservation(app_ready):
    c, uid = make_teacher(app_ready)
    rid = c.post("/api/rezervacije", json=rez_data(qty=10, tid=uid)).json()["id"]
    r = c.delete(f"/api/rezervacije/{rid}")
    assert r.status_code == 200


def test_delete_other_teachers_reservation_forbidden(app_ready):
    c1, uid1 = make_teacher(app_ready)
    c2, uid2 = make_teacher(app_ready)
    rid = c1.post("/api/rezervacije", json=rez_data(hour=3, prostor="ladja", tid=uid1)).json()["id"]
    r = c2.delete(f"/api/rezervacije/{rid}")
    assert r.status_code == 403


def test_admin_can_delete_any_reservation(app_ready, admin_client):
    c, uid = make_teacher(app_ready)
    rid = c.post("/api/rezervacije", json=rez_data(qty=10, tid=uid)).json()["id"]
    r = admin_client.delete(f"/api/rezervacije/{rid}")
    assert r.status_code == 200


# ═══ VARNOST ═══
def test_teacher_cannot_spoof_teacher_id(app_ready):
    """Učitelj ne sme ustvariti rezervacije v imenu drugega (IDOR fix)."""
    c, uid = make_teacher(app_ready)
    admin_id = get_user_id("admin")
    r = c.post("/api/rezervacije", json=rez_data(prostor="ladja", tid=admin_id))
    assert r.status_code == 403


def test_unauthenticated_redirected(app_ready):
    c = make_client()
    r = c.get("/api/rezervacije", follow_redirects=False)
    assert r.status_code == 307
    assert "/auth/login" in r.headers["location"]
