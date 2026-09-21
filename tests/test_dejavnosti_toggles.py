"""Pravila checkboxov v /dejavnosti (Vnos dejavnosti) — preverjanje stanja.

Pokriva vedenje, ki ga opisuje uporabnik:
  1. »Celoten dan« označen  → razredi se pojavijo kot dan dejavnosti (BlockedDate).
  2. »Celoten dan« + prostor → prostor je rezerviran za ta dan, ure 1–5.
  3. Odkljukamo prostor (full_day ostane) → rezervacija se samodejno prekliče,
     blokada (dan dejavnosti) pa ostane.
  4. Odkljukamo »Celoten dan« → razredi izginejo iz dneva dejavnosti (BlockedDate
     se odstrani) in tudi rezervacije se odstranijo.
"""

from datetime import date, timedelta

from app.database import SessionLocal
from app.models import ActivityDay, BlockedDate, Reservation
from tests.conftest import login

FUTURE = (date.today() + timedelta(days=7)).isoformat()
DAY = date.fromisoformat(FUTURE)


def _admin_login(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    return admin


def _count(model, **filters) -> int:
    db = SessionLocal()
    try:
        return db.query(model).filter_by(**filters).count()
    finally:
        db.close()


def _payload(**over):
    """Osnovni payload; over prepiše polja."""
    base = {
        "grade": "6",
        "section": "NARAVOSLOVNI",
        "title": "Oblak 365",
        "full_day": True,
        "date_from": FUTURE,
        "date_to": FUTURE,
        "classes": "6.a",
        "all_classes": False,
        "prostori": "racunalnica",
    }
    base.update(over)
    return base


# ── 1 + 2: osnovna sinhronizacija ────────────────────────────────────

def test_full_day_blocks_classes_and_reserves_room(client, make_user):
    _admin_login(client, make_user)
    r = client.post("/api/dejavnosti", json=_payload())
    assert r.status_code == 201, r.text
    # 6.a blokiran → pojavi se kot »Dejavnost« na koledarju
    assert _count(BlockedDate, razred="6.a", date=DAY) == 1
    # 1 prostor × 5 ur (1–5)
    assert _count(Reservation, date=DAY, prostor="racunalnica") == 5
    hours = _reservation_hours()
    assert hours == [1, 2, 3, 4, 5]


def _reservation_hours():
    db = SessionLocal()
    try:
        rows = db.query(Reservation).filter(Reservation.date == DAY).all()
        return sorted(r.hour for r in rows)
    finally:
        db.close()


# ── 3: odkljukamo prostor → rezervacija preklicana, blokada ostane ───

def test_uncheck_room_cancels_reservations_keeps_block(client, make_user):
    _admin_login(client, make_user)
    r = client.post("/api/dejavnosti", json=_payload())
    assert r.status_code == 201, r.text
    dej_id = r.json()["id"]
    assert _count(Reservation, date=DAY) == 5

    up = client.put(f"/api/dejavnosti/{dej_id}", json=_payload(prostori=""))
    assert up.status_code == 200, up.text

    # rezervacije so preklicane …
    assert _count(Reservation, date=DAY) == 0
    # … blokada (dan dejavnosti) pa ostane
    assert _count(BlockedDate, razred="6.a", date=DAY) == 1


# ── 4: odkljukamo »Celoten dan« → razredi izginejo iz dejavnosti ─────

def test_uncheck_full_day_removes_block_and_reservations(client, make_user):
    _admin_login(client, make_user)
    r = client.post("/api/dejavnosti", json=_payload())
    assert r.status_code == 201, r.text
    dej_id = r.json()["id"]
    assert _count(BlockedDate, date=DAY) == 1
    assert _count(Reservation, date=DAY) == 5

    up = client.put(f"/api/dejavnosti/{dej_id}", json=_payload(full_day=False))
    assert up.status_code == 200, up.text

    # razredi niso več dan dejavnosti → nič več na koledarju
    assert _count(BlockedDate, date=DAY) == 0
    assert _count(Reservation, date=DAY) == 0
    # dejavnost sama ostane shranjena
    assert _count(ActivityDay, id=dej_id) == 1


# ── 5: ponovno označimo »Celoten dan« → blokada se povrne ────────────

def test_recheck_full_day_restores_block(client, make_user):
    _admin_login(client, make_user)
    r = client.post("/api/dejavnosti", json=_payload(full_day=False))
    dej_id = r.json()["id"]
    assert _count(BlockedDate, date=DAY) == 0

    up = client.put(f"/api/dejavnosti/{dej_id}", json=_payload(full_day=True))
    assert up.status_code == 200, up.text
    assert _count(BlockedDate, razred="6.a", date=DAY) == 1


# ── 6: WordPress checkpoint — stanje se shrani, brez WP pa sporoči napako ──

