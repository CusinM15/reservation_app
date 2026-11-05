# 1. september: samodejni izbris rezervacij in ocenjevanj za nazaj.
# Dnevi dejavnosti (activity_days) OSTAJEJO.
from datetime import date

from app.database import SessionLocal
from app.models import ActivityDay, Assessment, Reservation
from app.school_year import purge_previous_school_year, school_year_cutoff
from tests.conftest import default_school_id


def _seed(sid, teacher_id):
    db = SessionLocal()
    try:
        db.add_all([
            Reservation(school_id=sid, prostor="P1", date=date(2026, 6, 15), hour=1,
                        teacher_id=teacher_id),
            Reservation(school_id=sid, prostor="P1", date=date(2026, 10, 1), hour=1,
                        teacher_id=teacher_id),
            Assessment(school_id=sid, razred="5.a", date=date(2026, 5, 20),
                       ponavljanje=False, teacher_id=teacher_id),
            Assessment(school_id=sid, razred="5.a", date=date(2026, 11, 3),
                       ponavljanje=False, teacher_id=teacher_id),
            ActivityDay(school_id=sid, grade="5", section="KULTURNI",
                        title="Kulturni dan", date_from=date(2026, 4, 10)),
        ])
        db.commit()
    finally:
        db.close()


def test_cutoff_meja(client):
    assert school_year_cutoff(date(2026, 9, 1)) == date(2026, 9, 1)
    assert school_year_cutoff(date(2026, 10, 15)) == date(2026, 9, 1)
    assert school_year_cutoff(date(2027, 3, 1)) == date(2026, 9, 1)
    assert school_year_cutoff(date(2026, 8, 31)) == date(2025, 9, 1)


def test_purge_izbrise_samo_za_nazaj_in_ohrani_dejavnosti(client, make_user):
    sid = default_school_id()
    teacher = make_user(role="teacher")
    _seed(sid, teacher.id)

    db = SessionLocal()
    try:
        rez = purge_previous_school_year(db, today=date(2026, 9, 1))
        assert rez["skipped"] is False
        assert rez["reservations"] == 1, rez
        assert rez["assessments"] == 1, rez
        # ostanejo: nova rezervacija, novo ocenjevanje, dejavnost
        assert db.query(Reservation).filter(Reservation.date >= date(2026, 9, 1)).count() == 1
        assert db.query(Assessment).filter(Assessment.date >= date(2026, 9, 1)).count() == 1
        assert db.query(ActivityDay).count() == 1
        # drugi zagon istega leta = no-op
        rez2 = purge_previous_school_year(db, today=date(2026, 9, 2))
        assert rez2["skipped"] is True
    finally:
        db.close()
