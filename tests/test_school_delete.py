# ─────────────────────────────────────────────────────────────────────────
# tests/test_school_delete.py — brisanje šole (gumb »Izbriši«, glavni admin)
#
# Zahteva: glavni admin ima gumb »Izbriši šolo«. Brisanje odstrani VSE podatke
# te šole (uporabnike, rezervacije, ocenjevanja, dneve dejavnosti, blokade,
# nastavitve, poti šole) in šolo samo. Podatki drugih šol ostanejo nedotaknjeni.
# Privzete šole ni mogoče izbrisati (bootstrap bi jo ob zagonu znova ustvaril).
# ─────────────────────────────────────────────────────────────────────────

from datetime import date

from app.config import settings as app_settings
from app.database import SessionLocal
from app.models import (
    ActivityDay, Assessment, AuditLog, BlockedDate, Reservation, School,
    SchoolAlias, SchoolSetting, User,
)
from app.tenancy import create_school
from tests.conftest import default_school_id, login

DAY = date(2026, 12, 15)


def _school_b_with_data(make_user):
    """Šola A (privzeta) z eno rezervacijo, šola B s polnim naborom podatkov."""
    sid_a = default_school_id()
    db = SessionLocal()
    try:
        school_b = create_school(db, name="Šola B", slug="solab")
        sid_b = school_b.id
        u = make_user(role="teacher", school_id=sid_b)
        db.add_all([
            Reservation(school_id=sid_a, prostor="tablice", date=DAY, hour=1,
                        teacher_id=1, qty=2),
            Reservation(school_id=sid_b, prostor="ladja", date=DAY, hour=1,
                        teacher_id=u.id, qty=1),
            Assessment(school_id=sid_b, razred="7.a", date=DAY, teacher_id=u.id),
            BlockedDate(school_id=sid_b, razred="7.a", date=DAY, created_by_id=u.id),
            ActivityDay(school_id=sid_b, grade="7", section="ŠPORTNI",
                        title="B dan", full_day=True),
        ])
        db.commit()
        return sid_a, sid_b, u.id
    finally:
        db.close()


def _count(model, sid):
    db = SessionLocal()
    try:
        return db.query(model).filter(model.school_id == sid).count()
    finally:
        db.close()


# ── 1. Srečna pot ─────────────────────────────────────────────────────

def test_delete_school_removes_all_its_data(client, make_user):
    sid_a, sid_b, _uid = _school_b_with_data(make_user)
    login(client, app_settings.MAIN_ADMIN_USERNAME, app_settings.MAIN_ADMIN_PASSWORD)

    r = client.delete(f"/api/schools/{sid_b}")
    assert r.status_code == 200, r.text
    assert "izbrisana" in r.json()["message"]
    assert r.json()["deleted"]["users"] >= 1

    db = SessionLocal()
    try:
        assert db.query(School).filter(School.id == sid_b).first() is None
        # vsi podatki šole B so izbrisani
        for model in (User, Reservation, Assessment, BlockedDate, ActivityDay,
                      SchoolAlias, SchoolSetting):
            assert db.query(model).filter(model.school_id == sid_b).count() == 0, model
        # šola A je nedotaknjena
        assert db.query(School).filter(School.id == sid_a).first() is not None
        assert db.query(Reservation).filter(Reservation.school_id == sid_a).count() == 1
        # dogodek je zabeležen (school_id=None, ker šole ni več)
        row = db.query(AuditLog).filter(AuditLog.action == "delete_school").first()
        assert row is not None
        assert row.school_id is None
        assert "Šola B" in (row.details or "")
    finally:
        db.close()


def test_delete_school_keeps_aliases_of_other_schools(client, make_user):
    sid_a, sid_b, _uid = _school_b_with_data(make_user)
    login(client, app_settings.MAIN_ADMIN_USERNAME, app_settings.MAIN_ADMIN_PASSWORD)
    client.delete(f"/api/schools/{sid_b}")
    assert _count(SchoolAlias, sid_a) >= 1
    # pot šole B ne deluje več, pot šole A pa
    assert client.get("/rezervacije_solab", follow_redirects=False).status_code == 404
    assert client.get("/rezervacije_ostcj", follow_redirects=False).status_code == 200


# ── 2. Varovalke ──────────────────────────────────────────────────────

def test_default_school_cannot_be_deleted(client, make_user):
    sid_a = default_school_id()
    login(client, app_settings.MAIN_ADMIN_USERNAME, app_settings.MAIN_ADMIN_PASSWORD)
    r = client.delete(f"/api/schools/{sid_a}")
    assert r.status_code == 400
    assert "ni mogoče izbrisati" in r.json()["detail"]
    assert _count(Reservation, sid_a) >= 0     # šola še obstaja
    db = SessionLocal()
    try:
        assert db.query(School).filter(School.id == sid_a).first() is not None
    finally:
        db.close()


def test_delete_school_school_admin_forbidden(client, make_user):
    _sid_a, sid_b, _uid = _school_b_with_data(make_user)
    admin = make_user(role="admin")            # šolski admin (šola A)
    login(client, admin.username)
    r = client.delete(f"/api/schools/{sid_b}")
    assert r.status_code == 403
    db = SessionLocal()
    try:
        assert db.query(School).filter(School.id == sid_b).first() is not None
    finally:
        db.close()


def test_delete_school_teacher_forbidden(client, make_user):
    _sid_a, sid_b, _uid = _school_b_with_data(make_user)
    teacher = make_user()
    login(client, teacher.username)
    assert client.delete(f"/api/schools/{sid_b}").status_code == 403


def test_delete_unknown_school_404(client, make_user):
    login(client, app_settings.MAIN_ADMIN_USERNAME, app_settings.MAIN_ADMIN_PASSWORD)
    assert client.delete("/api/schools/999999").status_code == 404
