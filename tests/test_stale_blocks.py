# ─────────────────────────────────────────────────────────────────────────
# tests/test_stale_blocks.py — ZASTARELE blokade dejavnosti
#
# Kontekst (napaka iz produkcije, 2026-09-23): 22. 10. so bile vse dejavnosti
# »Projekt Od tona do glasbe« označene kot NE-celodnevne (full_day=False), a je
# koledar vseeno izpisal razrede 6.a–9.c, ker so v blocked_dates ostale blokade
# od takrat, ko so bile dejavnosti (ali uvoz) celodnevne.
#
# Pravilo čiščenja (scripts/cleanup_stale_blocks.py): blokada (datum, razred) je
# zastarela LE, če jo pokriva vsaj en zapis ActivityDay iste šole IN noben izmed
# teh zapisov ni full_day. Blokade brez pokritja (ročni »Dnevi dejavnosti«)
# ostanejo.
# ─────────────────────────────────────────────────────────────────────────

import sys
from datetime import date

from app.database import SessionLocal
from app.models import ActivityDay, BlockedDate
from scripts.cleanup_stale_blocks import activity_pairs, stale_blocked_pairs
from tests.conftest import default_school_id

DAY = date(2026, 10, 22)


def _add_activity(db, sid, full_day, klasi, day=DAY):
    rec = ActivityDay(
        school_id=sid, grade="6", section="KULTURNI", title="Projekt",
        full_day=full_day,
        termini=[{"date": str(day), "classes": ",".join(klasi), "date_to": None}],
    )
    db.add(rec)
    db.commit()
    return rec


def _add_block(db, sid, razred, uid, day=DAY):
    db.add(BlockedDate(school_id=sid, razred=razred, date=day, created_by_id=uid))
    db.commit()


# ── 1. activity_pairs (razširjanje terminov) ──────────────────────────

def test_activity_pairs_expands_date_to_and_keeps_full_flag():
    rec = ActivityDay(
        grade="6", section="KULTURNI", title="t", full_day=True,
        termini=[{"date": "2026-10-22", "date_to": "2026-10-23", "classes": "6.a,6.b"}],
    )
    pairs = activity_pairs(rec)
    assert [(str(d), kl, f) for d, kl, f in pairs] == [
        ("2026-10-22", ["6.a", "6.b"], True),
        ("2026-10-23", ["6.a", "6.b"], True),
    ]


def test_activity_pairs_uses_date_from_when_no_termini():
    rec = ActivityDay(grade="6", section="KULTURNI", title="t", full_day=False,
                      date_from=DAY, classes="6.a")
    pairs = activity_pairs(rec)
    assert [(str(d), kl, f) for d, kl, f in pairs] == [("2026-10-22", ["6.a"], False)]


# ── 2. Zaznava zastarelih blokad ──────────────────────────────────────

def test_only_stale_blocks_are_detected(client, make_user):
    """Krajša dejavnost + blokada za isti (datum, razred) = zastarelo.
    Celodnevna dejavnost = pravilno. Blokada brez dejavnosti = ročna (ostane)."""
    u = make_user(role="admin")
    sid = default_school_id()
    db = SessionLocal()
    try:
        _add_activity(db, sid, full_day=False, klasi=["6.a"])
        _add_activity(db, sid, full_day=True, klasi=["6.b"])
        _add_block(db, sid, "6.a", u.id)     # zastarela
        _add_block(db, sid, "6.b", u.id)     # pravilna
        _add_block(db, sid, "6.c", u.id)     # ročna blokada (dejavnosti ni)

        assert stale_blocked_pairs(db, sid) == [(DAY, "6.a")]
    finally:
        db.close()


def test_full_day_activity_protects_class_that_also_has_short_one(client, make_user):
    """Če razred na isti dan pokriva TUDI celodnevna dejavnost, blokada ni
    zastarela (dan je res blokiran)."""
    u = make_user(role="admin")
    sid = default_school_id()
    db = SessionLocal()
    try:
        _add_activity(db, sid, full_day=False, klasi=["6.a"])
        _add_activity(db, sid, full_day=True, klasi=["6.a"])
        _add_block(db, sid, "6.a", u.id)
        assert stale_blocked_pairs(db, sid) == []
    finally:
        db.close()


# ── 3. Skript za čiščenje (CLI) ───────────────────────────────────────

def test_cleanup_script_dry_run_changes_nothing(client, make_user, capsys):
    u = make_user(role="admin")
    sid = default_school_id()
    db = SessionLocal()
    try:
        _add_activity(db, sid, full_day=False, klasi=["6.a"])
        _add_block(db, sid, "6.a", u.id)
    finally:
        db.close()

    from scripts import cleanup_stale_blocks as cs
    sys.argv = ["cleanup_stale_blocks.py", "--school-id", str(sid)]
    assert cs.main() == 0

    db = SessionLocal()
    try:
        assert db.query(BlockedDate).filter(BlockedDate.school_id == sid).count() == 1
    finally:
        db.close()


def test_cleanup_script_apply_removes_only_stale_and_logs(client, make_user):
    u = make_user(role="admin")
    sid = default_school_id()
    db = SessionLocal()
    try:
        _add_activity(db, sid, full_day=False, klasi=["6.a"])
        _add_activity(db, sid, full_day=True, klasi=["6.b"])
        _add_block(db, sid, "6.a", u.id)     # zastarela → izbrisana
        _add_block(db, sid, "6.b", u.id)     # pravilna → ostane
        _add_block(db, sid, "6.c", u.id)     # ročna → ostane
    finally:
        db.close()

    from scripts import cleanup_stale_blocks as cs
    sys.argv = ["cleanup_stale_blocks.py", "--apply", "--school-id", str(sid)]
    assert cs.main() == 0

    db = SessionLocal()
    try:
        left = {(str(b.date), b.razred) for b in
                db.query(BlockedDate).filter(BlockedDate.school_id == sid).all()}
        assert left == {("2026-10-22", "6.b"), ("2026-10-22", "6.c")}
        from app.models import AuditLog
        assert db.query(AuditLog).filter(AuditLog.action == "cleanup_stale_blocks").count() == 1
    finally:
        db.close()
