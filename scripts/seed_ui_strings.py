#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────
# scripts/seed_ui_strings.py — napolni tabelo ui_strings (SL/EN)
#
# Namen: v bazo zapiše napise gumbov in pogovornih oken v SLOVENŠČINI in
# ANGLEŠČINI. Aplikacija jih bere po ključu (glej app/i18n.py, {{ t('kljuc') }}),
# admin šole pa v Nastavitvah šole izbere jezik (UI_LANGUAGE).
#
# Seznam napisov je v scripts/ui_strings_data.py (en vir resnice).
#
# Uporaba:
#   python -m scripts.seed_ui_strings            # doda manjkajoče, posodobi obstoječe
#   python -m scripts.seed_ui_strings --dry-run  # samo pokaže, kaj bi naredil
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal          # noqa: E402
from app.i18n import invalidate_cache          # noqa: E402
from app.models import UIString                # noqa: E402
from scripts.ui_strings_data import STRINGS    # noqa: E402


def seed(db, *, dry_run: bool = False, keep_manual: bool = False) -> tuple[int, int]:
    """Dodaj/posodobi napise; vrni (dodano, posodobljeno)."""
    # Varnost: podvojeni ključi v STRINGS bi pri vstavljanju v bazo sprožili
    # UniqueViolation. Zato to prestrežemo tukaj z jasnim sporočilom.
    _seen: set[str] = set()
    _dups: set[str] = set()
    for _k, *_ in STRINGS:
        if _k in _seen:
            _dups.add(_k)
        else:
            _seen.add(_k)
    if _dups:
        raise ValueError(f"Podvojeni ključi v ui_strings_data.STRINGS: {', '.join(sorted(_dups))}")
    added = updated = 0
    for key, context, sl, en in STRINGS:
        row = db.query(UIString).filter(UIString.key == key).first()
        if row is None:
            added += 1
            if not dry_run:
                db.add(UIString(key=key, context=context, sl=sl, en=en))
        else:
            changed = False
            if keep_manual:
                # Ne prepisuj ročno vnesenih vrednosti (samo dopolni prazne).
                if (not row.sl) and sl:
                    row.sl = sl; changed = True
                if (not row.en) and en:
                    row.en = en; changed = True
            else:
                if row.sl != sl:
                    row.sl = sl; changed = True
                if row.en != en:
                    row.en = en; changed = True
                if (row.context or "") != context:
                    row.context = context; changed = True
            if changed:
                updated += 1
    if not dry_run:
        db.commit()
        invalidate_cache()
    return added, updated


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="seed_ui_strings",
                                     description="Napolni tabelo ui_strings (SL/EN).")
    parser.add_argument("--dry-run", action="store_true", help="ne zapiši v bazo")
    parser.add_argument("--keep-manual", action="store_true",
                        help="ne prepiši obstoječih (samo dopolni prazne)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    db = SessionLocal()
    try:
        added, updated = seed(db, dry_run=args.dry_run, keep_manual=args.keep_manual)
    finally:
        db.close()

    glagol = "bi dodal" if args.dry_run else "dodal"
    print(f"ui_strings: {glagol} {added}, {'bi posodobil' if args.dry_run else 'posodobil'} {updated} "
          f"(skupaj v seznamu {len(STRINGS)}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
