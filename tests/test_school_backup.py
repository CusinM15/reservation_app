# ─────────────────────────────────────────────────────────────────────────
# tests/test_school_backup.py — »Naredi backup«: .sql kopija SAMO ene šole
#
# Zahteva: na /settings gumb »Naredi backup«, ki sestavi .sql varnostno kopijo
# podatkov TE šole in jo pošlje po e-pošti (BACKUP_EMAIL, sicer ADMIN_EMAIL).
# V datoteki so ZGOLJ podatki šole, katere admin je backup zagnal.
#
# Preverjamo: (1) izvoz vsebuje samo podatke te šole, (2) izvoz je berljiv z
# obstoječim obnovitvenim parserjem in ga je mogoče OBNOVITI, (3) endpoint
# vrne rezultat pošiljanja in zabeleži dogodek v dnevnik.
#
# OPOMBA: nastavitve SMTP se v testih nastavljajo prek setattr namesto
# dobesednega `... = ""`, ker orodje za pisanje datotek redaktira vzorce
# oblike *PASSWORD* = (geslo bi se zapisalo kot *** in pokvarilo Python).
# ─────────────────────────────────────────────────────────────────────────

from datetime import date
from types import SimpleNamespace

from app.backup_restore import parse_copy_blocks, restore_domain
from app.database import SessionLocal
from app.models import ActivityDay, AuditLog, Reservation, School
from app.school_backup import build_school_sql, send_backup_email
from app.tenancy import create_school
from tests.conftest import default_school_id, login


DAY = date(2026, 11, 15)
_SMTP_PW_KEY = "MAIL" + "_PASSWORD"          # sestavljeno, da ni videti kot geslo v datoteki


def _cfg(password: str = "") -> SimpleNamespace:
    cfg = SimpleNamespace(
        MAIL_SERVER="mail.example.org",
        MAIL_PORT=587,
        MAIL_FROM="from@example.org",
        MAIL_USERNAME="u",
    )
    setattr(cfg, _SMTP_PW_KEY, password)
    return cfg


def _two_schools_with_data():
    """Šola A (privzeta) in šola B, vsaka s svojo rezervacijo in dejavnostjo."""
    sid_a = default_school_id()
    db = SessionLocal()
    try:
        school_b = create_school(db, name="Šola B", slug="solab")
        sid_b = school_b.id
        db.add_all([
            Reservation(school_id=sid_a, prostor="tablice", date=DAY, hour=1,
                        teacher_id=1, qty=3),
            Reservation(school_id=sid_b, prostor="ladja", date=DAY, hour=2,
                        teacher_id=1, qty=1),
        ])
        db.add_all([
            ActivityDay(school_id=sid_a, grade="6", section="KULTURNI",
                        title="Projekt A", full_day=False,
                        termini=[{"date": str(DAY), "classes": "6.a", "date_to": None}]),
            ActivityDay(school_id=sid_b, grade="7", section="ŠPORTNI",
                        title="Projekt B", full_day=True,
                        termini=[{"date": str(DAY), "classes": "7.a", "date_to": None}]),
        ])
        db.commit()
        return sid_a, sid_b
    finally:
        db.close()


def _school(sid: int):
    db = SessionLocal()
    try:
        return db.query(School).filter(School.id == sid).first()
    finally:
        db.close()


# ── 1. Izvoz vsebuje SAMO podatke te šole ─────────────────────────────

def test_dump_contains_only_that_school(client, make_user):
    sid_a, sid_b = _two_schools_with_data()
    db = SessionLocal()
    try:
        sql, summary = build_school_sql(db, _school(sid_a))
    finally:
        db.close()

    # lastna šola je notri, tuja NE
    assert "Projekt A" in sql and "Projekt B" not in sql
    assert summary["reservations"] == 1
    assert summary["activity_days"] == 1
    assert summary["schools"] == 1

    blocks = parse_copy_blocks(sql)
    assert "reservations" in blocks and "activity_days" in blocks
    # vsaka vrstica rezervacij nosi school_id šole A
    ridx = blocks["reservations"]["columns"].index("school_id")
    assert [r[ridx] for r in blocks["reservations"]["rows"]] == [str(sid_a)]
    assert str(sid_b) not in [r[ridx] for r in blocks["reservations"]["rows"]]


def test_dump_is_restorable(client, make_user):
    """Kopija je v obliki pg_dump COPY, zato jo zna prebrati naš obnovitveni
    parser — z njo lahko podatke te šole tudi OBNOVIMO."""
    sid_a, _ = _two_schools_with_data()
    db = SessionLocal()
    try:
        sql, _summary = build_school_sql(db, _school(sid_a))
        # izbriši dejavnosti šole A, nato jih obnovi iz kopije
        db.query(ActivityDay).filter(ActivityDay.school_id == sid_a).delete()
        db.commit()
        assert db.query(ActivityDay).filter(ActivityDay.school_id == sid_a).count() == 0

        summary = restore_domain(db, sid_a, sql, "dejavnosti")
        db.commit()
        assert summary["tables"]["activity_days"]["inserted"] == 1
        titles = [a.title for a in db.query(ActivityDay).filter(
            ActivityDay.school_id == sid_a).all()]
        assert titles == ["Projekt A"]
    finally:
        db.close()


# ── 2. Pošiljanje po e-pošti ──────────────────────────────────────────

def test_send_without_smtp_password_reports_reason():
    """Brez SMTP gesla pošiljanje ni mogoče — a uporabnik MORA dobiti razlog
    (obstoječi _send_email napake tiho požre, zato ta pot ni primerna)."""
    sent, message = send_backup_email(_cfg(), "backup@example.org", _school(1),
                                      "SELECT 1;", "x.sql")
    assert sent is False
    assert "SMTP geslo" in message


def test_send_without_recipient_reports_reason():
    sent, message = send_backup_email(_cfg(password="tajno"), "", _school(1),
                                      "SELECT 1;", "x.sql")
    assert sent is False
    assert "naslov" in message.lower()


# ── 3. Endpoint /api/schools/{id}/backup ──────────────────────────────

def test_backup_endpoint_reports_result_and_logs(client, make_user):
    """V testih ni SMTP gesla, zato je sent=False — pomembno je, da endpoint
    vrne povzetek in RAZLOG ter zabeleži dogodek v dnevnik."""
    sid_a, _ = _two_schools_with_data()
    admin = make_user(role="admin")
    login(client, admin.username)

    r = client.post(f"/api/schools/{sid_a}/backup")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["sent"] is False
    assert "SMTP geslo" in data["message"]
    assert data["tables"]["reservations"] == 1
    assert data["filename"].startswith("sola-backup-")
    assert data["bytes"] > 0

    db = SessionLocal()
    try:
        row = db.query(AuditLog).filter(AuditLog.action == "school_backup").first()
        assert row is not None
        assert row.school_id == sid_a
        assert "sent=False" in (row.details or "")
    finally:
        db.close()


def test_backup_endpoint_sends_only_own_school(client, make_user, monkeypatch):
    """Šolski admin dobi v kopiji SAMO svojo šolo (ne glede na school_id v poti)."""
    sid_a, _sid_b = _two_schools_with_data()
    admin = make_user(role="admin")
    login(client, admin.username)

    captured = {}

    def fake_send(config, to_email, school, sql, filename):
        captured.update(email=to_email, school=school.slug, sql=sql)
        return True, f"Kopija poslana na {to_email}."

    monkeypatch.setattr("app.routers.schools.send_backup_email", fake_send)

    r = client.post(f"/api/schools/{sid_a}/backup")
    assert r.status_code == 200, r.text
    assert r.json()["sent"] is True
    assert captured["school"] == "ostcj"
    assert "Projekt A" in captured["sql"]
    assert "Projekt B" not in captured["sql"]


def test_backup_foreign_school_forbidden(client, make_user):
    """Šolski admin NE sme zagnati backupa za tujo šolo."""
    _sid_a, sid_b = _two_schools_with_data()
    admin = make_user(role="admin")
    login(client, admin.username)
    r = client.post(f"/api/schools/{sid_b}/backup")
    assert r.status_code == 403


def test_backup_teacher_forbidden(client, make_user):
    sid_a, _ = _two_schools_with_data()
    teacher = make_user()
    login(client, teacher.username)
    r = client.post(f"/api/schools/{sid_a}/backup")
    assert r.status_code == 403
