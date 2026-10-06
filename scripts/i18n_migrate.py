#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────
# scripts/i18n_migrate.py — prehod predlog: trdo besedilo → {{ t('kljuc') }}
#
# Za vsak napis iz scripts/ui_strings_data.py poišče DOBESEDNO besedilo v
# predlogah (HTML besedilna vozlišča, npr. >Shrani< ali >\n  Shrani\n<) in ga
# zamenja s klicem {{ t('kljuc', 'Shrani') }}. Tako aplikacija napis prebere
# iz tabele ui_strings v izbranem jeziku.
#
# Uporaba:
#   python -m scripts.i18n_migrate             # zamenja in izpiše povzetek
#   python -m scripts.i18n_migrate --dry-run   # samo pokaže (nič ne spremeni)
#   python -m scripts.i18n_migrate --only index.html school_settings.html
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.ui_strings_data import STRINGS  # noqa: E402

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"


def build_map() -> dict[str, str]:
    """Vrni {slovensko_besedilo: ključ}. Ob dvojniku obdrži prvi ključ."""
    out: dict[str, str] = {}
    for key, _ctx, sl, _en in STRINGS:
        if sl and sl not in out:
            out[sl] = key
    return out


def migrate_text(text: str, smap: dict[str, str]) -> tuple[str, int]:
    """Zamenjaj besedilna vozlišča s t() klici. Vrni (novo_besedilo, št_zamenjav)."""
    count = 0

    # Daljša besedila najprej (da se ne ujamemo na krajše podnize).
    for sl in sorted(smap, key=len, reverse=True):
        key = smap[sl]
        # >  OBLIKA  <  (ohrani morebitne presledke/prelome okoli besedila)
        pattern = re.compile(r'>(\s*)' + re.escape(sl) + r'(\s*)<')

        def _sub(m, key=key, sl=sl):
            nonlocal count
            count += 1
            return f">{m.group(1)}{{{{ t('{key}', '{sl}') }}}}{m.group(2)}<"

        text = pattern.sub(_sub, text)
    return text, count


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="i18n_migrate",
                                     description="Predloge: besedilo → {{ t('kljuc') }}")
    parser.add_argument("--dry-run", action="store_true", help="nič ne zapiši")
    parser.add_argument("--only", nargs="*", default=None,
                        help="samo te datoteke (privzeto: vse *.html)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    smap = build_map()
    files = sorted(TEMPLATES_DIR.glob("*.html"))
    if args.only:
        files = [f for f in files if f.name in set(args.only)]

    total = 0
    for path in files:
        # newline="" → prelomi vrstic (CRLF/LF) se OHRANIJO, da diff ostane majhen.
        with open(path, "r", encoding="utf-8", newline="") as fh:
            original = fh.read()
        updated, n = migrate_text(original, smap)
        if n:
            if not args.dry_run:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(updated)
            total += n
            print(f"{'[dry] ' if args.dry_run else ''}{path.name}: {n} zamenjav")
    print(f"\nSkupaj {total} zamenjav v {len(files)} predlogah "
          f"({'DRY-RUN' if args.dry_run else 'zapisano'}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
