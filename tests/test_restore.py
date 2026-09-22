# ─────────────────────────────────────────────────────────────────────────
# tests/test_restore.py — obnova podatkov iz .sql varnostne kopije
#
# Preverja:
#   1. Obnova rezervacij zamenja vrstice TE šole in se ne dotakne drugih šol.
#   2. Vrstice drugih šol v kopiji se preskočijo (ne mešamo podatkov).
#   3. Obnova dejavnosti (activity_days + blocked_dates), vključno s stolpcem
#      JSONB (termini).
#   4. Neveljavne datoteke so zavrnjene z jasno napako (ne 500).
#
# Zakaj lastni .sql vzorci? Ker je oblika, ki jo beremo, izpis `pg_dump -F p`
# (COPY ... FROM stdin). Vzorci so majhni in berljivi, zato je jasno, kaj
# obnova pričakuje.
# ─────────────────────────────────────────────────────────────────────────

from datetime import date

from app.database import SessionLocal
from app.tenancy import create_school
from tests.conftest import login, default_school_id

TAB = "\t"


def _copy_block(table: str, columns: list[str], rows: list[list[str]]) -> str:
    """Sestavi en COPY blok v obliki, kot jo zapiše pg_dump."""
    head = f"COPY public.{table} ({', '.join(columns)}) FROM stdin;"
    body = "\n".join(TAB.join(r) for r in rows)
    return "\n".join([head, body, r"\."]) + "\n"


def _count(model, **filters) -> int:
    db = SessionLocal()
    try:
        return db.query(model).filter_by(**filters).count()
    finally:
        db.close()


def _admin_login(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    return admin


# ── 1. + 2. Rezervacije: zamenjava + ohranitev drugih šol ─────────────

def test_restore_rezervacije_replaces_only_this_school(client, make_user):
    from app.models import Reservation

    sid = default_school_id()
    db = SessionLocal()
    try:
        school_b = create_school(db, name="Druga šola", slug="drugi")
    finally:
        db.close()

    # Šola B ima svojo rezervacijo (ki se je obnova ne sme dotakniti)
    db = SessionLocal()
    try:
        db.add(Reservation(school_id=school_b.id, prostor="tablice", date=date(2026, 10, 2),
                           hour=1, teacher_id=1, qty=3))
        db.commit()
    finally:
        db.close()
    assert _count(Reservation, school_id=school_b.id) == 1

    admin = _admin_login(client, make_user)
    # Najprej naredi eno rezervacijo te šole prek API-ja (da imamo kaj izbrisati)
    client.post("/api/rezervacije", json={
        "date": (date.today()).isoformat(), "hour": 0, "prostor": "tablice",
        "qty": 5, "teacher_id": 999,
    })
    assert _count(Reservation, school_id=sid) == 1

    columns = ["id", "prostor", "date", "hour", "razred", "qty", "teacher_id",
               "series_id", "name", "school_id"]
    rows = [
        ["1", "tablice", "2026-10-01", "0", "5.a", "10", "1", r"\N", r"\N", str(sid)],
        ["2", "racunalnica", "2026-10-01", "2", r"\N", r"\N", "1", r"\N", "Dogodek", str(sid)],
        # vrstica DRUGE šole v isti kopiji → mora biti preskočena
        ["3", "ladja", "2026-10-01", "3", r"\N", r"\N", "1", r"\N", r"\N", str(school_b.id)],
    ]
    sql = _copy_block("reservations", columns, rows)

    r = client.post(
        f"/api/schools/{sid}/restore",
        data={"domain": "rezervacije"},
        files={"file": ("backup.sql", sql, "text/plain")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tables"]["reservations"]["inserted"] == 2
    assert body["tables"]["reservations"]["deleted"] == 1
    assert body["skipped_other_schools"] == 1

    # te šole so zdaj vrstice iz kopije, druga šola nespremenjena
    assert _count(Reservation, school_id=sid) == 2
    assert _count(Reservation, school_id=school_b.id) == 1
    assert _count(Reservation, school_id=sid, prostor="racunalnica") == 1
    assert _count(Reservation, school_id=sid, name="Dogodek") == 1


def test_restore_backup_without_school_column_goes_to_this_school(client, make_user):
    """Starejše kopije (pred večšolsko prenovo) nimajo school_id — vse vrstice
    pripadajo tej šoli."""
    from app.models import Assessment

    sid = default_school_id()
    _admin_login(client, make_user)

    columns = ["id", "razred", "date", "ponavljanje", "teacher_id"]
    rows = [
        ["1", "5.a", "2026-10-05", "f", "1"],
        ["2", "5.b", "2026-10-06", "t", "1"],
    ]
    sql = _copy_block("assessments", columns, rows)

    r = client.post(
        f"/api/schools/{sid}/restore",
        data={"domain": "ocenjevanje"},
        files={"file": ("old.sql", sql, "text/plain")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["tables"]["assessments"]["inserted"] == 2
    assert _count(Assessment, school_id=sid) == 2
    assert _count(Assessment, school_id=sid, razred="5.b", ponavljanje=True) == 1


# ── 3. Dejavnosti (activity_days + blocked_dates, JSONB) ──────────────

def test_restore_dejavnosti_restores_both_tables(client, make_user):
    from app.models import ActivityDay, BlockedDate

    sid = default_school_id()
    _admin_login(client, make_user)

    act_cols = ["id", "grade", "section", "title", "full_day", "recurring", "date_from",
                "date_undetermined", "all_classes", "source", "termini", "school_id"]
    act_rows = [
        ["1", "5", "TEHNIŠKI", "Tehniški dan", "t", "f", "2026-10-08",
         "f", "t", "manual",
         '[{"date": "2026-10-08", "classes": "5.a"}]', str(sid)],
    ]
    blk_cols = ["id", "razred", "date", "created_by_id", "school_id"]
    blk_rows = [
        ["1", "5.a", "2026-10-08", "1", str(sid)],
        ["2", "5.b", "2026-10-08", "1", str(sid)],
    ]
    sql = _copy_block("activity_days", act_cols, act_rows) + _copy_block("blocked_dates", blk_cols, blk_rows)

    r = client.post(
        f"/api/schools/{sid}/restore",
        data={"domain": "dejavnosti"},
        files={"file": ("b.sql", sql, "text/plain")},
    )
    assert r.status_code == 200, r.text
    tables = r.json()["tables"]
    assert tables["activity_days"]["inserted"] == 1
    assert tables["blocked_dates"]["inserted"] == 2

    assert _count(ActivityDay, school_id=sid) == 1
    assert _count(BlockedDate, school_id=sid) == 2
    # JSONB stolpec se je prenesel kot struktura (ne kot goli niz)
    db = SessionLocal()
    try:
        rec = db.query(ActivityDay).filter(ActivityDay.school_id == sid).first()
        assert isinstance(rec.termini, list)
        assert rec.termini[0]["classes"] == "5.a"
    finally:
        db.close()


# ── 4. Starejša shema: manjkajoči obvezni stolpci ─────────────────────

def test_restore_fills_missing_not_null_boolean_columns(client, make_user):
    """Kopija iz starejše sheme nima novega stolpca (npr. recurring), ki je v
    trenutni shemi OBVEZEN. Za bool/številke/nize ga zapolnimo z varno
    vrednostjo in obnova uspe (namesto napake NotNullViolation)."""
    from app.models import ActivityDay

    sid = default_school_id()
    _admin_login(client, make_user)

    # recurring in date_undetermined namenoma manjkata
    act_cols = ["id", "grade", "section", "title", "full_day", "date_from", "source", "school_id"]
    act_rows = [["1", "6", "KULTURNI", "Kulturni dan", "t", "2026-10-12", "manual", str(sid)]]
    sql = _copy_block("activity_days", act_cols, act_rows)

    r = client.post(
        f"/api/schools/{sid}/restore",
        data={"domain": "dejavnosti"},
        files={"file": ("old.sql", sql, "text/plain")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tables"]["activity_days"]["inserted"] == 1
    filled = body["filled_columns"]["activity_days"]
    assert "recurring" in filled and "date_undetermined" in filled
    assert "all_classes" in filled
    # evidenca (created_at/updated_at) se zapolni s trenutnim časom
    assert "created_at" in filled and "updated_at" in filled

    db = SessionLocal()
    try:
        rec = db.query(ActivityDay).filter(ActivityDay.school_id == sid).first()
        assert rec.recurring is False
        assert rec.date_undetermined is False
        assert rec.title == "Kulturni dan"
    finally:
        db.close()


def test_restore_rejects_backup_missing_required_date_column(client, make_user):
    """Obveznega datuma ne izmišljujemo — javimo jasno napako."""
    sid = default_school_id()
    _admin_login(client, make_user)
    # reservations.date je NOT NULL in brez privzete vrednosti
    sql = _copy_block("reservations", ["id", "prostor", "hour", "teacher_id", "school_id"],
                      [["1", "tablice", "0", "1", str(sid)]])
    r = client.post(
        f"/api/schools/{sid}/restore",
        data={"domain": "rezervacije"},
        files={"file": ("old.sql", sql, "text/plain")},
    )
    assert r.status_code == 400
    assert "manjkajo obvezni stolpci" in r.json()["detail"]
    assert "date" in r.json()["detail"]


# ── 5. Neveljavne datoteke ────────────────────────────────────────────

def test_restore_rejects_file_without_copy_blocks(client, make_user):
    sid = default_school_id()
    _admin_login(client, make_user)
    r = client.post(
        f"/api/schools/{sid}/restore",
        data={"domain": "rezervacije"},
        files={"file": ("x.sql", "CREATE TABLE foo (id int);\n", "text/plain")},
    )
    assert r.status_code == 400
    assert "ni prepoznanih podatkov" in r.json()["detail"]


def test_restore_rejects_insert_format(client, make_user):
    sid = default_school_id()
    _admin_login(client, make_user)
    r = client.post(
        f"/api/schools/{sid}/restore",
        data={"domain": "rezervacije"},
        files={"file": ("x.sql", "INSERT INTO public.reservations (id) VALUES (1);\n", "text/plain")},
    )
    assert r.status_code == 400
    assert "INSERT" in r.json()["detail"]


def test_restore_requires_valid_domain(client, make_user):
    sid = default_school_id()
    _admin_login(client, make_user)
    r = client.post(
        f"/api/schools/{sid}/restore",
        data={"domain": "nekaj"},
        files={"file": ("x.sql", "COPY public.reservations (id) FROM stdin;\n1\n\\.\n", "text/plain")},
    )
    assert r.status_code == 400
    assert "Neveljavno področje" in r.json()["detail"]


def test_restore_teacher_forbidden(client, make_user):
    sid = default_school_id()
    teacher = make_user()          # teacher nima pravic
    login(client, teacher.username)
    r = client.post(
        f"/api/schools/{sid}/restore",
        data={"domain": "rezervacije"},
        files={"file": ("x.sql", "COPY public.reservations (id) FROM stdin;\n1\n\\.\n", "text/plain")},
    )
    assert r.status_code == 403