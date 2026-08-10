# ─────────────────────────────────────────────────────────────────────────
# tests/test_rezervacije.py — Rezervacije prostorov: ustvarjanje,
# kapaciteta tablic, ekskluzivnost, preteklost, spoofing, brisanje
# ─────────────────────────────────────────────────────────────────────────

from datetime import date, timedelta
import json

from tests.conftest import login

FUTURE = (date.today() + timedelta(days=7)).isoformat()
PAST = (date.today() - timedelta(days=7)).isoformat()
H = {"Content-Type": "application/json"}
# teacher_id je obvezen v shemi (frontend ga pošilja), ampak server ga
# vedno override-a iz seje — 999 je namerno napačen, da testiramo to.
TID = 999


def _create(client, payload, expected=201):
    payload = {**payload, "teacher_id": TID}
    r = client.post("/api/rezervacije", json=payload)
    assert r.status_code == expected, f"pričakovan {expected}, dobil {r.status_code}: {r.text}"
    return r


# ── Ustvarjanje ────────────────────────────────────────────────────────

def test_create_tablice_with_qty(client, make_user):
    u = make_user()
    login(client, u.username)
    r = _create(client, {"date": FUTURE, "hour": 0, "prostor": "tablice", "razred": "5.a", "qty": 10})
    assert r.json()["teacher_id"] == u.id
    assert r.json()["qty"] == 10


def test_create_all_rooms(client, make_user):
    u = make_user()
    login(client, u.username)
    for i, prostor in enumerate(["tablice", "racunalnica", "ladja", "gospodinjska-ucilnica"]):
        payload = {"date": FUTURE, "hour": i, "prostor": prostor, "razred": "5.a"}
        if prostor == "tablice":
            payload["qty"] = 5
        r = _create(client, payload)
        assert r.json()["prostor"] == prostor


def test_create_without_login_redirects(client):
    r = client.post("/api/rezervacije", json={"date": FUTURE, "hour": 0, "prostor": "ladja"}, follow_redirects=False)
    assert r.status_code == 307  # middleware preusmeri na login (RedirectResponse default 307)


# ── Kapaciteta in validacije ───────────────────────────────────────────

def test_tablice_requires_qty(client, make_user):
    u = make_user()
    login(client, u.username)
    _create(client, {"date": FUTURE, "hour": 0, "prostor": "tablice", "razred": "5.a"}, expected=400)


def test_tablice_qty_over_max(client, make_user):
    u = make_user()
    login(client, u.username)
    r = _create(client, {"date": FUTURE, "hour": 0, "prostor": "tablice", "razred": "5.a", "qty": 29}, expected=400)
    assert "kapaciteto" in r.json()["detail"]


def test_tablice_capacity_sum(client, make_user):
    """20 + 15 = 35 > 28 → drugi poskus zavrnjen."""
    u = make_user()
    login(client, u.username)
    _create(client, {"date": FUTURE, "hour": 1, "prostor": "tablice", "razred": "5.a", "qty": 20})
    r = _create(client, {"date": FUTURE, "hour": 1, "prostor": "tablice", "razred": "5.b", "qty": 15}, expected=400)
    assert "presega kapaciteto" in r.json()["detail"]


def test_exclusive_room_duplicate(client, make_user):
    u = make_user()
    login(client, u.username)
    _create(client, {"date": FUTURE, "hour": 2, "prostor": "racunalnica", "razred": "5.a"})
    r = _create(client, {"date": FUTURE, "hour": 2, "prostor": "racunalnica", "razred": "5.b"}, expected=400)
    assert "zaseden" in r.json()["detail"]


def test_tablice_not_exclusive(client, make_user):
    """Dva učitelja lahko hkrati rezervirata tablice (dokler je kapaciteta)."""
    u = make_user()
    login(client, u.username)
    _create(client, {"date": FUTURE, "hour": 3, "prostor": "tablice", "razred": "5.a", "qty": 10})
    _create(client, {"date": FUTURE, "hour": 3, "prostor": "tablice", "razred": "5.b", "qty": 10})


def test_past_date_rejected(client, make_user):
    u = make_user()
    login(client, u.username)
    r = _create(client, {"date": PAST, "hour": 0, "prostor": "ladja", "razred": "5.a"}, expected=400)
    assert "preteklosti" in r.json()["detail"]


def test_invalid_hour_rejected(client, make_user):
    u = make_user()
    login(client, u.username)
    _create(client, {"date": FUTURE, "hour": 8, "prostor": "ladja", "razred": "5.a"}, expected=422)


def test_invalid_prostor_rejected(client, make_user):
    u = make_user()
    login(client, u.username)
    r = _create(client, {"date": FUTURE, "hour": 0, "prostor": "telovadnica", "razred": "5.a"}, expected=400)
    assert "Neveljaven prostor" in r.json()["detail"]


# ── Varnost: spoofing ──────────────────────────────────────────────────

def test_teacher_id_always_from_session(client, make_user):
    """Client poskuša poslati tuj teacher_id — server ga mora ignorirati."""
    u = make_user()
    login(client, u.username)
    r = _create(client, {"date": FUTURE, "hour": 4, "prostor": "ladja", "razred": "5.a", "teacher_id": 999})
    assert r.json()["teacher_id"] == u.id, "teacher_id ne sme biti iz requesta!"


def test_assessment_teacher_id_from_session(client, make_user):
    u = make_user()
    login(client, u.username)
    r = client.post("/api/ocenjevanja", json={"date": FUTURE, "razred": "5.a", "ponavljanje": False, "teacher_id": 999})
    assert r.status_code == 201, r.text
    assert r.json()["teacher_id"] == u.id

# ── Brisanje ───────────────────────────────────────────────────────────

def test_delete_own_reservation(client, make_user):
    u = make_user()
    login(client, u.username)
    rid = _create(client, {"date": FUTURE, "hour": 0, "prostor": "ladja", "razred": "5.a"}).json()["id"]
    r = client.delete(f"/api/rezervacije/{rid}")
    assert r.status_code == 200
    assert client.get(f"/api/rezervacije?date={FUTURE}").status_code == 200


def test_delete_others_reservation_forbidden(client, make_user):
    u1 = make_user(username="teacher_a")
    u2 = make_user(username="teacher_b")
    # u1 ustvari rezervacijo
    login(client, u1.username)
    rid = _create(client, {"date": FUTURE, "hour": 0, "prostor": "ladja", "razred": "5.a"}).json()["id"]
    # u2 jo poskuša izbrisati
    client.post("/auth/logout")
    login(client, u2.username)
    r = client.delete(f"/api/rezervacije/{rid}")
    assert r.status_code == 403
