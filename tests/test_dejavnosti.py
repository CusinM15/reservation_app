# ─────────────────────────────────────────────────────────────────────────
# tests/test_dejavnosti.py — UI "Vnos dejavnosti" (activity_days):
# CRUD, dovoljenja (samo vodstvo/admin), sinhronizacija z blocked_dates
# in rezervacijami ter preklic ocenjevanja ob danem datumu.
# ─────────────────────────────────────────────────────────────────────────

from datetime import date, timedelta

from app.database import SessionLocal
from app.models import BlockedDate, Reservation, ActivityDay, Assessment
from tests.conftest import login

TODAY = date.today()
FUTURE = (TODAY + timedelta(days=7)).isoformat()
H = {"Content-Type": "application/json"}


def _admin_login(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    return admin


def _vodstvo_login(client, make_user):
    vod = make_user(role="vodstvo")
    login(client, vod.username)
    return vod


def _teacher_login(client, make_user):
    t = make_user(role="teacher")
    login(client, t.username)
    return t


def _count(model, **filters) -> int:
    db = SessionLocal()
    try:
        return db.query(model).filter_by(**filters).count()
    finally:
        db.close()


# ── Ustvarjanje (brez sinhronizacije) ────────────────────────────────

def test_create_dejavnost_undetermined(client, make_user):
    _admin_login(client, make_user)
    r = client.post("/api/dejavnosti", json={
        "grade": "1", "section": "KULTURNI",
        "title": "Prešernov dan", "full_day": False,
        "date_undetermined": True, "date_text": "februar",
        "all_classes": True, "prostori": "", "cena": "", "vodja": "uč. SLJ",
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["title"] == "Prešernov dan"
    assert data["date_undetermined"] is True


def test_create_dejavnost_default_title(client, make_user):
    """Če naslov ni podan, se ustvari privzeti '{section} {grade}. razred'."""
    _admin_login(client, make_user)
    r = client.post("/api/dejavnosti", json={
        "grade": "3", "section": "ŠPORTNI", "title": "",
        "full_day": True, "date_from": FUTURE, "prostori": "ladja",
        "all_classes": False, "classes": "3.a,3.b",
    })
    assert r.status_code == 201, r.text
    assert r.json()["title"] == "ŠPORTNI 3. razred"


# ── Sync: sinhronizacija z blocked_dates in rezervacij ──────────────

def test_full_day_sync_creates_blocked_and_reservations(client, make_user):
    _admin_login(client, make_user)
    r = client.post("/api/dejavnosti", json={
        "grade": "6", "section": "NARAVOSLOVNI", "title": "Oblak",
        "full_day": True, "date_from": FUTURE, "date_to": FUTURE,
        "prostori": "racunalnica,ladja", "all_classes": False, "classes": "6.a,6.b",
    })
    assert r.status_code == 201, r.text
    # blocked_dates: 2 razreda * 1 dan = 2
    assert _count(BlockedDate, date=date.fromisoformat(FUTURE)) == 2
    # rezervacije: 2 prostora * 5 ur (1–5) * 1 dan = 10
    assert _count(Reservation, date=date.fromisoformat(FUTURE)) == 10


def test_multi_datum_sync_via_termini(client, make_user):
    """Termini (več datumov, vsak s svojimi razredi) ustvari blokade + rezervacije za vsak datum."""
    _admin_login(client, make_user)
    from datetime import timedelta
    d1 = (date.today() + timedelta(days=10)).isoformat()
    d2 = (date.today() + timedelta(days=11)).isoformat()
    r = client.post("/api/dejavnosti", json={
        "grade": "7", "section": "TEHNIŠKI", "title": "Računalniško opismenjevanje",
        "full_day": True, "prostori": "racunalnica",
        "all_classes": False, "classes": "7.a",
        "date_undetermined": False,
        "termini": [
            {"date": d1, "classes": "7.a"},
            {"date": d2, "classes": "7.b"},
        ],
    })
    assert r.status_code == 201, r.text
    # blocked: 7.a na d1 + 7.b na d2 = 2
    assert _count(BlockedDate, date=date.fromisoformat(d1), razred="7.a") == 1
    assert _count(BlockedDate, date=date.fromisoformat(d2), razred="7.b") == 1
    # rezervacije: 1 prostor * 5 ur za 2 datuma = 10
    assert _count(Reservation, date=date.fromisoformat(d1)) == 5
    assert _count(Reservation, date=date.fromisoformat(d2)) == 5
    # termini so shranjeni na zapis
    dej = r.json()
    assert len(dej["termini"]) == 2


def test_termini_range_expands_dates(client, make_user):
    """Termin z date_to (obseg) ustvari blokade + rezervacije za VSE dni v obsegu."""
    _admin_login(client, make_user)
    d1 = (date.today() + timedelta(days=15)).isoformat()
    d2 = (date.today() + timedelta(days=17)).isoformat()  # 3 dni: d1, d1+1, d2
    r = client.post("/api/dejavnosti", json={
        "grade": "7", "section": "TEHNIŠKI", "title": "Obseg",
        "full_day": True, "prostori": "racunalnica",
        "all_classes": False, "classes": "7.a", "date_undetermined": False,
        "termini": [{"date": d1, "date_to": d2, "classes": "7.a"}],
    })
    assert r.status_code == 201, r.text
    # blocked: 7.a na vseh 3 dneh = 3
    assert _count(BlockedDate, razred="7.a") == 3
    # rezervacije: 1 prostor * 5 ur * 3 dni = 15
    assert _count(Reservation, date=date.fromisoformat(d1)) == 5
    assert _count(Reservation, date=date.fromisoformat(d2)) == 5


def test_reservations_not_duplicated_on_resave(client, make_user):
    """Večkratno shranjevanje iste dejavnosti (isto ime/datum/uro) ne sme podvojiti rezervacij."""
    _admin_login(client, make_user)
    from datetime import timedelta
    d1 = (date.today() + timedelta(days=10)).isoformat()
    body = {
        "grade": "7", "section": "TEHNIŠKI", "title": "Oblak 365",
        "full_day": True, "prostori": "racunalnica",
        "all_classes": False, "classes": "7.a", "date_undetermined": False,
        "termini": [{"date": d1, "classes": "7.a"}],
    }
    r1 = client.post("/api/dejavnosti", json=body)
    assert r1.status_code == 201, r1.text
    first = _count(Reservation, date=date.fromisoformat(d1))
    assert first == 5  # 1 prostor * 5 ur

    # shrani znova (ista vsebina) → rezervacije se ne smejo podvojiti
    r2 = client.post("/api/dejavnosti", json=body)
    assert r2.status_code == 201, r2.text
    second = _count(Reservation, date=date.fromisoformat(d1))
    assert second == first, f"rezervacije so se podvojile: {first} → {second}"
    assert second == 5


def test_sync_cancels_assessment_and_emails(client, make_user):
    admin = _admin_login(client, make_user)
    teacher = make_user(role="teacher", email="teacher@test.si")
    db = SessionLocal()
    try:
        db.add(Assessment(razred="5.a", date=date.fromisoformat(FUTURE), teacher_id=teacher.id))
        db.commit()
    finally:
        db.close()
    assert _count(Assessment, razred="5.a", date=date.fromisoformat(FUTURE)) == 1

    r = client.post("/api/dejavnosti", json={
        "grade": "5", "section": "TEHNIŠKI", "title": "Opazujem",
        "full_day": True, "date_from": FUTURE,
        "prostori": "gospodinjska-ucilnica", "all_classes": True,
    })
    assert r.status_code == 201, r.text
    # ocenjevanje za 5.a na ta dan se izbriše
    assert _count(Assessment, razred="5.a", date=date.fromisoformat(FUTURE)) == 0


# ── Dovoljenja ───────────────────────────────────────────────────────

def test_teacher_forbidden(client, make_user):
    # clean_db resetira users identiteto → prvi user dobi id=1 (v ALLOWED_USER_IDS 1-4).
    # Zato najprej zasedemo ID-je 1-4, da teacher dobi id >= 5 in res pade na vlogo.
    for _ in range(4):
        make_user(role="admin")
    teacher = _teacher_login(client, make_user)
    assert teacher.id >= 5
    r = client.post("/api/dejavnosti", json={
        "grade": "1", "section": "KULTURNI", "title": "X", "full_day": False,
    })
    assert r.status_code == 403


def test_vodstvo_allowed(client, make_user):
    _vodstvo_login(client, make_user)
    r = client.post("/api/dejavnosti", json={
        "grade": "2", "section": "KULTURNI", "title": "Filmska", "full_day": False,
        "date_undetermined": True, "date_text": "december",
    })
    assert r.status_code == 201, r.text


# ── Posodobitev in brisanje ──────────────────────────────────────────

def test_update_and_delete(client, make_user):
    _admin_login(client, make_user)
    r = client.post("/api/dejavnosti", json={
        "grade": "4", "section": "KULTURNI", "title": "Gledališče",
        "full_day": False, "date_undetermined": True, "date_text": "april",
    })
    assert r.status_code == 201, r.text
    dej_id = r.json()["id"]

    up = client.put(f"/api/dejavnosti/{dej_id}", json={
        "grade": "4", "section": "ŠPORTNI", "title": "Plavanje",
        "full_day": True, "date_from": FUTURE, "prostori": "ladja",
        "all_classes": True,
    })
    assert up.status_code == 200, up.text
    assert up.json()["section"] == "ŠPORTNI"
    assert up.json()["title"] == "Plavanje"

    dl = client.delete(f"/api/dejavnosti/{dej_id}")
    assert dl.status_code == 200
    assert _count(ActivityDay, id=dej_id) == 0


def test_delete_nonexistent_404(client, make_user):
    _admin_login(client, make_user)
    r = client.delete("/api/dejavnosti/99999")
    assert r.status_code == 404