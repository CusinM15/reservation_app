# ─────────────────────────────────────────────────────────────────────────
# tests/test_nightly_backups.py — nočni backup: VSAKA šola svojo kopijo
#
# Zahteva: ponoči mora vsaka šola (vse šole, ki jih ima glavni admin) dobiti
# SVOJO varnostno kopijo — in vsaka kopija vsebuje ZGOLJ podatke te šole.
#
# Zakaj nov skript? Prejšnji `scripts/db_backup.py` je klical `pg_dump`, ki ga
# v sliki NI (job je zato vsako noč tiho odpovedal), poleg tega bi pg_dump
# izvozil CELO bazo (vse šole v eni datoteki).
# ─────────────────────────────────────────────────────────────────────────

from datetime import date
from pathlib import Path

from app.database import SessionLocal
from app.models import ActivityDay, AuditLog, Reservation, School
from app.tenancy import create_school
from scripts.school_backups import backup_all_schools, run
from tests.conftest import default_school_id


DAY = date(2026, 12, 15)


def _two_schools():
    sid_a = default_school_id()
    db = SessionLocal()
    try:
        b = create_school(db, name="Šola B", slug="solab")
        sid_b = b.id
        db.add_all([
            Reservation(school_id=sid_a, prostor="tablice", date=DAY, hour=1,
                        teacher_id=1, qty=2),
            Reservation(school_id=sid_b, prostor="ladja", date=DAY, hour=1,
                        teacher_id=1, qty=1),
            ActivityDay(school_id=sid_a, grade="6", section="KULTURNI",
                        title="Dejavnost A", full_day=False,
                        termini=[{"date": str(DAY), "classes": "6.a", "date_to": None}]),
            ActivityDay(school_id=sid_b, grade="7", section="ŠPORTNI",
                        title="Dejavnost B", full_day=True,
                        termini=[{"date": str(DAY), "classes": "7.a", "date_to": None}]),
        ])
        db.commit()
        return sid_a, sid_b
    finally:
        db.close()


def _smtp_pw_key():
    return "MAIL" + "_PASSWORD"


def test_every_school_gets_own_dump(client, make_user):
    """Vsaka šola dobi SVOJO kopijo, ki vsebuje le njene podatke."""
    sid_a, sid_b = _two_schools()
    calls = []

    def fake_send(config, to_email, school, sql, filename):
        calls.append({"school_id": school.id, "slug": school.slug, "email": to_email,
                      "sql": sql, "filename": filename})
        return True, f"Kopija poslana na {to_email}."

    db = SessionLocal()
    try:
        results = backup_all_schools(db, send_fn=fake_send)
    finally:
        db.close()

    assert len(calls) == 2, "vsaka šola mora dobiti svojo kopijo"
    by_sid = {c["school_id"]: c for c in calls}
    assert set(by_sid) == {sid_a, sid_b}

    # izolacija: kopija šole A ne vsebuje vrstic šole B in obratno
    assert "Dejavnost A" in by_sid[sid_a]["sql"]
    assert "Dejavnost B" not in by_sid[sid_a]["sql"]
    assert "Dejavnost B" in by_sid[sid_b]["sql"]
    assert "Dejavnost A" not in by_sid[sid_b]["sql"]

    # rezultat za vsako šolo + povzetek vrstic
    assert all(r["sent"] for r in results)
    assert all(r["tables"]["reservations"] == 1 for r in results)
    assert {r["slug"] for r in results} == {"ostcj", "solab"}


def test_nightly_run_logs_each_school(client, make_user):
    """Vsak zagon zabeleži dogodek v dnevnik TE šole (z oznako nightly)."""
    sid_a, sid_b = _two_schools()

    def ok_send(config, to_email, school, sql, filename):
        return True, "ok"

    db = SessionLocal()
    try:
        backup_all_schools(db, send_fn=ok_send)
        rows = db.query(AuditLog).filter(AuditLog.action == "school_backup").all()
        assert len(rows) == 2
        assert all("nightly=True" in (r.details or "") for r in rows)
        assert {r.school_id for r in rows} == {sid_a, sid_b}
        assert all(r.username == "sistem:nočni-backup" for r in rows)
    finally:
        db.close()


def test_run_exit_codes(client, make_user, monkeypatch):
    """run() vrne 0, ko vse pošlje, in 1, ko katera kopija spodleti
    (CronJob je OnFailure, zato mora napaka biti vidna)."""
    _two_schools()

    monkeypatch.setattr(
        "scripts.school_backups.send_backup_email",
        lambda config, to_email, school, sql, filename: (True, "ok"),
    )
    assert run() == 0

    monkeypatch.setattr(
        "scripts.school_backups.send_backup_email",
        lambda config, to_email, school, sql, filename: (False, "SMTP geslo ni nastavljeno"),
    )
    assert run() == 1


def test_run_uses_school_recipient(client, make_user, monkeypatch):
    """Prejemnik je naslov TE šole (BACKUP_EMAIL šole, sicer ADMIN_EMAIL)."""
    from app.tenancy import get_school_config
    _two_schools()
    seen = {}

    def capture(config, to_email, school, sql, filename):
        seen[school.slug] = to_email
        return True, "ok"

    monkeypatch.setattr("scripts.school_backups.send_backup_email", capture)
    assert run() == 0
    db = SessionLocal()
    try:
        for slug in ("ostcj", "solab"):
            school = db.query(School).filter(School.slug == slug).first()
            cfg = get_school_config(db, school.id)
            assert seen[slug] == (cfg.BACKUP_EMAIL or cfg.ADMIN_EMAIL)
    finally:
        db.close()


def test_nightly_cronjob_calls_new_script():
    """Regresijska varovalka: CronJob ne sme več klicati starega
    `scripts.db_backup` (pg_dump v sliki ne obstaja → job je tiho odpovedal)."""
    manifest = Path("k8s/app/base/sola-backup-cronjob.yaml").read_text(encoding="utf-8")
    assert "- scripts.school_backups" in manifest
    # komentar sme omeniti stari skript, UKAZ pa ne
    assert "- scripts.db_backup" not in manifest
    assert "-m\n            - scripts.school_backups" in manifest


def test_daily_report_is_removed():
    """Dnevno poročilo (sola-daily-report) je bilo odstranjeno 2026-09-23 —
    manifesta ni več, kustomizacija pa ga ne sme (več) vsebovati (sicer bi se
    ob `kubectl apply -k` CronJob znova ustvaril)."""
    assert not Path("k8s/app/base/sola-daily-report-cronjob.yaml").exists()
    kust = Path("k8s/app/base/kustomization.yaml").read_text(encoding="utf-8")
    assert "sola-daily-report" not in kust
