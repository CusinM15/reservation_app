#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────
# scripts/cleanup_stale_blocks.py — odstrani ZASTARELE blokade dejavnosti
#
# Zakaj: blokada (blocked_dates) se ustvari SAMO ob »Celoten dan« na dejavnosti.
# Če je bila dejavnost nekoč celodnevna (ali je nastala iz starega uvoza, preden
# je obstajala sinhronizacija v obe smeri), v bazi ostane blokada za razrede,
# ki jih pokriva dejavnost z full_day=False. Posledice:
#   * koledar ocenjevanj v vijoličnem polju izpiše razrede, čeprav dejavnost ne
#     blokira dneva;
#   * ocenjevanja na ta dan so po nepotrebnem zavrnjena (400).
#
# Pravilo (namerno konzervativno): blokado (datum, razred) štejemo za
# ZASTARELO le, če
#   1) jo pokriva vsaj en zapis ActivityDay ISTE ŠOLE (torej vemo, od kod je), IN
#   2) noben izmed teh zapisov ni full_day.
# Blokade, ki jih nobena dejavnost ne pokriva (ročno dodani »Dnevi dejavnosti«),
# se NIKOLI ne brišejo.
#
# Uporaba:
#   python3 scripts/cleanup_stale_blocks.py            # samo izpis (dry-run)
#   python3 scripts/cleanup_stale_blocks.py --apply    # izbriše + zapiše v dnevnik
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.audit import log_audit                     # noqa: E402
from app.database import SessionLocal               # noqa: E402
from app.models import ActivityDay, BlockedDate     # noqa: E402


def _as_date(value) -> date | None:
    """Pretvori ISO-niz/datum v date; neveljavno → None."""
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _date_range(start: date, end: date | None):
    """Vrni vsak datum od start do end (vključno); brez end → samo start."""
    cur = start
    while True:
        yield cur
        if not end or cur >= end:
            return
        cur += timedelta(days=1)


def activity_pairs(rec: ActivityDay) -> list[tuple[date, list[str], bool]]:
    """Vrni [(datum, razredi, full_day)] za en zapis dejavnosti.

    Uporablja enako logiko kot strežnik (_collect_pairs_from_rec): `termini`
    (z morebitnim `date_to`), sicer `date_from` + `classes`.
    """
    out: list[tuple[date, list[str], bool]] = []
    if rec.termini:
        for t in rec.termini:
            start = _as_date(t.get("date") or rec.date_from)
            if start is None:
                continue
            klasi = [o.strip() for o in str(t.get("classes") or "").split(",") if o.strip()]
            end = _as_date(t.get("date_to"))
            for d in _date_range(start, end):
                out.append((d, klasi, bool(rec.full_day)))
    else:
        start = _as_date(rec.date_from)
        if start is not None:
            klasi = [o.strip() for o in str(rec.classes or "").split(",") if o.strip()]
            out.append((start, klasi, bool(rec.full_day)))
    return out


def stale_blocked_pairs(db, school_id: int | None = None) -> list[tuple[date, str]]:
    """Vrni [(datum, razred)] blokad, ki so zastarele (glej pravilo v glavi)."""
    # (datum, razred) → seznam full_day zastavic dejavnosti, ki par pokrivajo
    covered: dict[tuple[date, str], list[bool]] = {}
    q = db.query(ActivityDay)
    if school_id is not None:
        q = q.filter(ActivityDay.school_id == school_id)
    for rec in q.all():
        for d, klasi, full in activity_pairs(rec):
            for odd in klasi:
                covered.setdefault((d, odd), []).append(full)

    stale: list[tuple[date, str]] = []
    bq = db.query(BlockedDate)
    if school_id is not None:
        bq = bq.filter(BlockedDate.school_id == school_id)
    for row in bq.all():
        flags = covered.get((row.date, row.razred))
        if flags and not any(flags):
            stale.append((row.date, row.razred))
    return sorted(stale)


def main() -> int:
    parser = argparse.ArgumentParser(description="Odstrani zastarele blokade dejavnosti.")
    parser.add_argument("--apply", action="store_true",
                        help="resnično izbriši (brez tega je samo izpis)")
    parser.add_argument("--school-id", type=int, default=None,
                        help="omeji na eno šolo (privzeto vse šole)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stale = stale_blocked_pairs(db, args.school_id)
        if not stale:
            print("Ni zastarelih blokad. Nič za narediti.")
            return 0

        print(f"Zastarelih blokad: {len(stale)}")
        for d, odd in stale:
            print(f"  {d}  {odd}")

        if not args.apply:
            print("\n(dry-run — nič ni bilo izbrisano; dodaj --apply za izbris)")
            return 0

        removed = 0
        for d, odd in stale:
            q = db.query(BlockedDate).filter(
                BlockedDate.date == d, BlockedDate.razred == odd)
            if args.school_id is not None:
                q = q.filter(BlockedDate.school_id == args.school_id)
            for row in q.all():
                db.delete(row)
                removed += 1
        log_audit(
            db, None, "sistem:cleanup_stale_blocks", "cleanup_stale_blocks",
            f"removed={removed}, school_id={args.school_id}, "
            f"dates={sorted({str(d) for d, _ in stale})}",
            school_id=args.school_id,
        )
        db.commit()
        print(f"\nIzbrisanih blokad: {removed} (zapisano v dnevnik dogodkov).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
