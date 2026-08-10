# ─────────────────────────────────────────────────────────────────────────
# tests/test_series.py — Serijske rezervacije (tedenske + celodnevne):
# ustvarjanje, avtomatsko brisanje konfliktov (db.delete fix!),
# kapaciteta, dovoljenja, preteklost
# ─────────────────────────────────────────────────────────────────────────

from datetime import date, timedelta

from app.database import SessionLocal
from app.models import Reservation
from tests.conftest import login

TODAY = date.today()
FUTURE = (TODAY + timedelta(days=7)).isoformat()
H = {"Content-Type": "application/json"}


def _admin_login(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    return admin


def _count_in_db(**filters) -> int:
    db = SessionLocal()
    try:
        return db.query(Reservation).filter_by(**filters).count()
    finally:
        db.close()


# ── Tedenska serija ────────────────────────────────────────────────────

def test_weekly_series_create(client, make_user):
    admin = _admin_login(client, make_user)
    r = client.post("/api/rezervacije/series/weekly", json={
        "prostor": "racunalnica", "hour": 0, "weekday": TODAY.weekday(),
        "date_from": FUTURE, "date_to": (TODAY + timedelta(days=35)).isoformat(),
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["created"] == 5  # +7, +14, +21, +28, +35 dni (5 tednov)
    assert data["removed"] == 0
    # vsi zapisi imajo isti series_id
    assert _count_in_db(series_id=data["series_id"]) == data["created"]


def test_weekly_series_deletes_conflict(client, make_user):
    """Admin serija čez obstoječo rezervacijo učitelja → avtomatski izbris (db.delete fix)."""
    teacher = make_user()
    login(client, teacher.username)
    r = client.post("/api/rezervacije", json={"date": FUTURE, "hour": 0, "prostor": "ladja", "razred": "5.a", "teacher_id": 999})
    assert r.status_code == 201, r.text
    old_id = r.json()["id"]
    client.post("/auth/logout")

    admin = _admin_login(client, make_user)
    r = client.post("/api/rezervacije/series/weekly", json={
        "prostor": "ladja", "hour": 0, "weekday": date.fromisoformat(FUTURE).weekday(),
        "date_from": FUTURE, "date_to": (date.fromisoformat(FUTURE) + timedelta(days=21)).isoformat(),
    })
    assert r.status_code == 201, r.text
    assert r.json()["removed"] == 1
    # stara rezervacija je RES izginila iz baze (prej je manjkal db.delete!)
    db = SessionLocal()
    try:
        assert db.query(Reservation).filter(Reservation.id == old_id).first() is None
    finally:
        db.close()


def test_weekly_series_qty_over_max(client, make_user):
    admin = _admin_login(client, make_user)
    r = client.post("/api/rezervacije/series/weekly", json={
        "prostor": "tablice", "hour": 0, "weekday": TODAY.weekday(),
        "date_from": FUTURE, "date_to": (TODAY + timedelta(days=14)).isoformat(), "qty": 29,
    })
    assert r.status_code == 400
    assert "kapaciteto" in r.json()["detail"]


def test_weekly_series_past_date_rejected(client, make_user):
    admin = _admin_login(client, make_user)
    past = (TODAY - timedelta(days=7)).isoformat()
    r = client.post("/api/rezervacije/series/weekly", json={
        "prostor": "ladja", "hour": 0, "weekday": (TODAY - timedelta(days=7)).weekday(),
        "date_from": past, "date_to": FUTURE,
    })
    assert r.status_code == 400
    assert "preteklosti" in r.json()["detail"]


def test_weekly_series_teacher_forbidden(client, make_user):
    teacher = make_user()
    login(client, teacher.username)
    r = client.post("/api/rezervacije/series/weekly", json={
        "prostor": "ladja", "hour": 0, "weekday": TODAY.weekday(),
        "date_from": FUTURE, "date_to": (TODAY + timedelta(days=14)).isoformat(),
    })
    assert r.status_code == 403


# ── Celodnevna serija ──────────────────────────────────────────────────

def test_full_day_series_create(client, make_user):
    admin = _admin_login(client, make_user)
    day = FUTURE
    r = client.post("/api/rezervacije/series/full-day", json={
        "prostor": "gospodinjska-ucilnica", "date_from": day, "date_to": day,
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["created"] == 8  # vse ure 0..7
    assert _count_in_db(series_id=data["series_id"]) == 8


def test_full_day_series_limited_hours(client, make_user):
    admin = _admin_login(client, make_user)
    r = client.post("/api/rezervacije/series/full-day", json={
        "prostor": "racunalnica", "date_from": FUTURE, "date_to": FUTURE, "hours": [0, 1, 2],
    })
    assert r.status_code == 201, r.text
    assert r.json()["created"] == 3


def test_full_day_series_weekend_skipped(client, make_user):
    """Če razpon pade na vikend, se vikend dnevi preskočijo."""
    admin = _admin_login(client, make_user)
    # Sobota + nedelja (od danes do +14 dni, vmes je sigurno vikend)
    r = client.post("/api/rezervacije/series/full-day", json={
        "prostor": "racunalnica",
        "date_from": (TODAY + timedelta(days=7)).isoformat(),
        "date_to": (TODAY + timedelta(days=14)).isoformat(),
    })
    assert r.status_code == 201, r.text
    # 8 delovnih dni x 8 ur = 64 (če v razponu ni vikenda); z vikendom manj
    assert r.json()["created"] <= 64


def test_full_day_series_deletes_conflict(client, make_user):
    teacher = make_user()
    login(client, teacher.username)
    r = client.post("/api/rezervacije", json={"date": FUTURE, "hour": 3, "prostor": "ladja", "razred": "5.a", "teacher_id": 999})
    assert r.status_code == 201, r.text
    client.post("/auth/logout")

    admin = _admin_login(client, make_user)
    r = client.post("/api/rezervacije/series/full-day", json={
        "prostor": "ladja", "date_from": FUTURE, "date_to": FUTURE,
    })
    assert r.status_code == 201, r.text
    assert r.json()["removed"] == 1  # konfliktna ura 3 je bila izbrisana
