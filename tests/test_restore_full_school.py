# ─────────────────────────────────────────────────────────────────────────
# tests/test_restore_full_school.py — obnova CELOTNE šole iz varnostne kopije
#
# Zahteva uporabnika (2026-09-23): »pri uvozu iz backupov tudi uvozi vse, tako
# da uvozi razrede, prostore, uporabnike. Torej zgradi celoten app z vsemi
# podatki iz backupov.«
#
# Preverjamo:
#   * kopija NE vsebuje več STANJE_MAIL (odvečni naslov za stanje sistema),
#   * obnova »vse« vrne uporabnike (z gesli), nastavitve (razredi/prostori),
#     dejavnosti, blokade, rezervacije in ocenjevanja,
#   * sklici na uporabnike (teacher_id, created_by_id) se PRESLIKAJOl na nove
#     id-je — sicer bi rezervacije kazale na napačne učitelje,
#   * obnova posameznega področja (uporabniki / nastavitve) deluje samostojno.
# ─────────────────────────────────────────────────────────────────────────

from datetime import date
from uuid import uuid4

from sqlalchemy import text as sql_text

from app.backup_restore import restore_domain
from app.database import SessionLocal
from app.models import (
    ActivityDay, Assessment, AuditLog, BlockedDate, Reservation, School, SchoolSetting, User,
)
from app.routers.auth import verify_password
from app.school_backup import build_school_sql
from app.tenancy import create_school, set_school_setting
from tests.conftest import TEST_PASSWORD, default_school_id, login

DAY = date(2026, 11, 20)


def _wipe_school(db, sid: int):
    """Izbriše vse podatke šole (vrstni red zaradi tujih ključev)."""
    for model in (Reservation, Assessment, BlockedDate, ActivityDay):
        db.query(model).filter(model.school_id == sid).delete()
    db.query(SchoolSetting).filter(SchoolSetting.school_id == sid).delete()
    db.execute(
        sql_text(
            "UPDATE audit_log SET user_id = NULL WHERE user_id IN "
            "(SELECT id FROM users WHERE school_id = :sid)"
        ), {"sid": sid},
    )
    db.query(User).filter(User.school_id == sid).delete()
    db.commit()


def _school_with_everything(make_user):
    """Šola B z uporabniki, nastavitvami in podatki — polna slika za obnovo.

    Slug je unikaten za vsak zagon, ker se testna baza med testi ne prazni
    (sicer bi drugi zagon padel na UNIQUE omejitvi slug-a).
    """
    sid = default_school_id()
    db = SessionLocal()
    try:
        school = create_school(db, name="Šola B", slug=f"solab{uuid4().hex[:6]}")
        sid_b = school.id
        teacher = make_user(role="teacher", school_id=sid_b)
        # create_school že vseje privzete nastavitve (RAZREDI, PROSTORI …), zato
        # jih nastavljamo prek set_school_setting (upsert), ne z INSERT.
        set_school_setting(db, sid_b, "RAZREDI", "6.a,6.b,7.a")
        set_school_setting(db, sid_b, "PROSTORI", "tablice,ladja")
        set_school_setting(db, sid_b, "STANJE_MAIL", "stanje@test.si")
        db.add_all([
            Reservation(school_id=sid_b, prostor="ladja", date=DAY, hour=1,
                        teacher_id=teacher.id, qty=2),
            Assessment(school_id=sid_b, razred="7.a", date=DAY, teacher_id=teacher.id),
            BlockedDate(school_id=sid_b, razred="7.a", date=DAY, created_by_id=teacher.id),
            ActivityDay(school_id=sid_b, grade="7", section="ŠPORTNI", title="B dan",
                        full_day=True, created_by_id=teacher.id),
        ])
        db.commit()
        return sid_b, teacher.id, teacher.username
    finally:
        db.close()


def _dump(sid: int) -> str:
    db = SessionLocal()
    try:
        school = db.query(School).filter(School.id == sid).first()
        sql, _summary = build_school_sql(db, school)
        return sql
    finally:
        db.close()


# ── 1. Kopija ne vsebuje več naslova za stanje ────────────────────────

def test_backup_excludes_stanje_mail(client, make_user):
    sid_b, _uid, _uname = _school_with_everything(make_user)
    sql = _dump(sid_b)
    assert "RAZREDI" in sql and "PROSTORI" in sql        # nastavitve SO v kopiji
    assert "STANJE_MAIL" not in sql, "naslova za stanje v kopiji ne potrebujemo"
    assert "stanje@test.si" not in sql


# ── 2. Obnova CELOTNE šole ────────────────────────────────────────────

def test_restore_all_rebuilds_whole_school(client, make_user):
    sid_b, old_uid, username = _school_with_everything(make_user)
    sql = _dump(sid_b)

    db = SessionLocal()
    try:
        _wipe_school(db, sid_b)
        # res smo brez vsega
        assert db.query(User).filter(User.school_id == sid_b).count() == 0
        assert db.query(Reservation).filter(Reservation.school_id == sid_b).count() == 0

        summary = restore_domain(db, sid_b, sql, "vse", fallback_user_id=1)
        db.commit()

        # uporabniki (z geslom)
        users = db.query(User).filter(User.school_id == sid_b).all()
        assert [u.username for u in users] == [username]
        assert verify_password(TEST_PASSWORD, users[0].password_hash)
        new_uid = users[0].id

        # sklici so preslikani na nov id uporabnika
        res = db.query(Reservation).filter(Reservation.school_id == sid_b).one()
        assert res.teacher_id == new_uid
        assert db.query(Assessment).filter(
            Assessment.school_id == sid_b).one().teacher_id == new_uid
        assert db.query(BlockedDate).filter(
            BlockedDate.school_id == sid_b).one().created_by_id == new_uid
        assert db.query(ActivityDay).filter(
            ActivityDay.school_id == sid_b).one().created_by_id == new_uid

        # nastavitve: razredi in prostori nazaj, STANJE_MAIL pa NE
        keys = {s.key for s in db.query(SchoolSetting).filter(
            SchoolSetting.school_id == sid_b).all()}
        assert {"RAZREDI", "PROSTORI"} <= keys
        assert "STANJE_MAIL" not in keys
        razredi = db.query(SchoolSetting).filter(
            SchoolSetting.school_id == sid_b, SchoolSetting.key == "RAZREDI").one()
        assert razredi.value == "6.a,6.b,7.a"

        assert summary["id_map_size"] >= 1
        assert summary["tables"]["users"]["inserted"] == 1
    finally:
        db.close()


def test_restore_does_not_touch_other_schools(client, make_user):
    sid_a = default_school_id()
    sid_b, _uid, _uname = _school_with_everything(make_user)
    sql = _dump(sid_b)

    db = SessionLocal()
    try:
        before = db.query(User).filter(User.school_id == sid_a).count()
        _wipe_school(db, sid_b)
        restore_domain(db, sid_b, sql, "vse", fallback_user_id=1)
        db.commit()
        assert db.query(User).filter(User.school_id == sid_a).count() == before
    finally:
        db.close()


# ── 3. Posamezna področja ─────────────────────────────────────────────

def test_restore_users_only(client, make_user):
    sid_b, _uid, username = _school_with_everything(make_user)
    sql = _dump(sid_b)
    db = SessionLocal()
    try:
        _wipe_school(db, sid_b)
        summary = restore_domain(db, sid_b, sql, "uporabniki", fallback_user_id=1)
        db.commit()
        assert summary["tables"]["users"]["inserted"] == 1
        assert db.query(User).filter(User.school_id == sid_b).count() == 1
        # rezervacije se pri tem področju NE obnavljajo
        assert db.query(Reservation).filter(Reservation.school_id == sid_b).count() == 0
    finally:
        db.close()


def test_restore_settings_only_restores_razredi_and_prostori(client, make_user):
    sid_b, _uid, _uname = _school_with_everything(make_user)
    sql = _dump(sid_b)
    db = SessionLocal()
    try:
        _wipe_school(db, sid_b)
        summary = restore_domain(db, sid_b, sql, "nastavitve", fallback_user_id=1)
        db.commit()
        assert summary["tables"]["school_settings"]["inserted"] >= 2
        keys = {s.key for s in db.query(SchoolSetting).filter(
            SchoolSetting.school_id == sid_b).all()}
        assert {"RAZREDI", "PROSTORI"} <= keys
        assert "STANJE_MAIL" not in keys
    finally:
        db.close()


# ── 4. Prek API-ja (kot iz UI) ────────────────────────────────────────

def test_restore_all_as_school_admin_keeps_session(client, make_user):
    """PRIJAVLJEN ŠOLSKI ADMIN OBNOVI SVOJO ŠOLO (uporabniki se zamenjajo → nov id).

    To je primer iz produkcije: obnova je uspela, stran pa je javila 500, ker je
    dnevnik dogodkov poskušal zapisati s STARIM id-jem uporabnika, ki je bil prav
    v tej obnovi izbrisan (tuji ključ). Seja mora ostati veljavna.
    """
    sid_b, _uid, _uname = _school_with_everything(make_user)
    admin_b = make_user(role="admin", school_id=sid_b)
    sql = _dump(sid_b)

    login(client, admin_b.username)
    # seja deluje pred obnovo
    assert client.get(f"/settings?school_id={sid_b}").status_code == 200

    r = client.post(
        f"/api/schools/{sid_b}/restore",
        data={"domain": "vse"},
        files={"file": ("b.sql", sql, "text/plain")},
    )
    assert r.status_code == 200, r.text

    # sea mora veljati naprej (piškotek se obnovi z novim id-jem)
    assert client.get(f"/settings?school_id={sid_b}").status_code == 200
    assert client.get("/history").status_code == 200

    db = SessionLocal()
    try:
        # dnevnik je zabeležen in ne visi na izbrisanem uporabniku
        row = (db.query(AuditLog)
                 .filter(AuditLog.action == "restore_from_backup",
                         AuditLog.school_id == sid_b)
                 .order_by(AuditLog.id.desc()).first())
        assert row is not None
        assert row.username == admin_b.username
        if row.user_id is not None:
            assert db.query(User).filter(User.id == row.user_id).first() is not None
    finally:
        db.close()


def test_restore_endpoint_returns_summary_and_logs(client, make_user):
    from app.config import settings
    from app.models import AuditLog
    sid_b, _uid, _uname = _school_with_everything(make_user)
    sql = _dump(sid_b)

    # Glavni admin (vidi vse šole) — šolski admin šole A ne sme obnavljati šole B.
    login(client, settings.MAIN_ADMIN_USERNAME, settings.MAIN_ADMIN_PASSWORD)
    db = SessionLocal()
    try:
        _wipe_school(db, sid_b)
    finally:
        db.close()

    r = client.post(
        f"/api/schools/{sid_b}/restore",
        data={"domain": "vse"},
        files={"file": ("b.sql", sql, "text/plain")},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["tables"]["users"]["inserted"] == 1
    assert data["tables"]["school_settings"]["inserted"] >= 2
    assert data["tables"]["reservations"]["inserted"] == 1

    db = SessionLocal()
    try:
        assert db.query(AuditLog).filter(
            AuditLog.action == "restore_from_backup",
            AuditLog.school_id == sid_b).count() >= 1
    finally:
        db.close()


# ── 5. Regresijski test: rezervni (fallback) id se po re-insertu uporabnikov ──
#    Obnova »vse« IZBRIŠE in znova vstavi vse uporabnike šole z NOVIM id-jem.
#    Če obnavlja šolski admin (npr. id 81), se ta po re-insertu preseli na drug id.
#    Vsaka rezervacija z učiteljem, ki ga v kopiji NI, je prej padla na STARI id
#    admina (81), ki po brisanju ne obstaja več → ForeignKeyViolation teacher_id=81.
#    (Produkcijski incident pri obnovi OŠ Toneta Čufarja, 2026-10-25.)

def _raw_backup_with_admin_and_unknown_teacher(sid_b: int, admin_username: str) -> str:
    """Ročna pg_dump-CLO kopija: user = le admin šole; rezervacija = neobstoječ učitelj.

    Rezervacija sklicuje na teacher_id 424242, ki NI v kopiji uporabnikov → pri
    obnovi pade na rezervni (fallback) račun, torej na admina, ki obnavlja.
    """
    # Vrstica users (COPY tab-ločena): id, username, email, first, last, hash, role, is_active, reset_token, school_id
    user_line = f"10\t{admin_username}\ta@b\t\t\tp\tadmin\tt\t\t{sid_b}"
    # Vrstica reservations: id, prostor, date, hour, razred, qty, teacher_id, series_id, name, school_id
    res_line = f"1\ttablice\t2026-09-25\t6\t\t23\t424242\t\\N\t\\N\t{sid_b}"
    return (
        "BEGIN;\n"
        "COPY public.users (id,username,email,first_name,last_name,password_hash,role,is_active,reset_token,school_id) FROM stdin;\n"
        f"{user_line}\n"
        "\\.\n"
        "COPY public.reservations (id,prostor,date,hour,razred,qty,teacher_id,series_id,name,school_id) FROM stdin;\n"
        f"{res_line}\n"
        "\\.\n"
        "COMMIT;\n"
    )


def test_restore_all_fallback_points_to_fresh_admin_id(client, make_user):
    """Obnova 'vse', ki jo izvaja ŠOLSKI ADMIN same šole, ne sme pasti na FK.

    Prej: admin (fallback) je imel v bazi id npr. 81; obnova je izbrisala in
    znova vstavila uporabnike z NOVIM id-jem, rezervacija z manjkajočim
    učiteljem pa je še vedno kazala na STARI id 81 → ForeignKeyViolation.
    Zdaj: id rezervnega računa se po re-insertu preračuna na svež id.
    """
    sid_b, _uid, _uname = _school_with_everything(make_user)
    db = SessionLocal()
    try:
        # Počisti vse podatke šole (kot sveža šola), nato ustvari admina — ta
        # mora OBSTOJATI, ko restore_domain ugotavlja njegovo uporabniško ime
        # PRED svojim internim brisanjem uporabnikov.
        _wipe_school(db, sid_b)
        admin_b = make_user(role="admin", school_id=sid_b)
        backup = _raw_backup_with_admin_and_unknown_teacher(sid_b, admin_b.username)
        old_fallback_id = admin_b.id
        assert db.query(User).filter(User.school_id == sid_b).count() == 1
        # restore_domain ZA "vse" sam izbriše in znova vstavi uporabnike šole
        summary = restore_domain(db, sid_b, backup, "vse", fallback_user_id=old_fallback_id)
        db.commit()

        # Rezervacija obstaja in teacher_id kaže na KOREN uporabnika (svež admin id)
        res = db.query(Reservation).filter(Reservation.school_id == sid_b).one()
        fresh = db.query(User).filter(User.id == res.teacher_id).one()
        assert fresh.username == admin_b.username
        # fallback_used=1: ravno neznani učitelj je padel na rezervo (admina)
        assert summary["tables"]["reservations"]["fallback_used"] == 1
        assert summary["tables"]["reservations"]["inserted"] == 1
    finally:
        db.close()
