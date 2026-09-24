#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────
# scripts/school_backups.py — backup: za VSAKO šolo svoja kopija
#
# Namen: CronJob `sola-db-backup` ponoči za VSAKO šolo posebej sestavi .sql
# varnostno kopijo in jo pošlje po e-pošti na naslov te šole (BACKUP_EMAIL,
# sicer ADMIN_EMAIL). Vsaka datoteka vsebuje ZGOLJ podatke svoje šole.
#
# Zakaj lasten izvoz in ne `pg_dump`?
#   * v sliki NI `pg_dump`/`psql` odjemalca (prejšnji `scripts/db_backup.py` je
#     zato vsako noč tiho odpovedal — pg_dump ni obstajal);
#   * `pg_dump` izvozi CELO bazo, torej bi ena datoteka vsebovala podatke VSEH
#     šol — tu pa mora vsaka šola dobiti SAMO SVOJE podatke.
# Izpis je zato v obliki `pg_dump -F p` (COPY bloki), ki jo zna prebrati naš
# obnovitveni parser — kopijo je mogoče obnoviti prek /settings → »Obnova iz
# varnostne kopije«.
#
# Uporaba:
#   python -m scripts.school_backups                                  # pošlji po e-pošti
#   python -m scripts.school_backups --save backup/ --no-email        # samo datoteke (test obnove)
#   python -m scripts.school_backups --school ostcj --save backup/    # ena šola, datoteka + mail
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.audit import log_audit                                   # noqa: E402
from app.database import SessionLocal                             # noqa: E402
from app.models import School                                     # noqa: E402
from app.school_backup import (                                   # noqa: E402
    backup_filename,
    build_school_sql,
    send_backup_email,
)
from app.tenancy import get_school_config                         # noqa: E402


def backup_all_schools(
    db,
    send_fn=None,
    save_dir: str | None = None,
    email: bool = True,
    only: str | int | None = None,
) -> list[dict]:
    """Za vsako šolo sestavi .sql (samo njeni podatki), jo po potrebi shrani in pošlje.

    Args:
        db: SQLAlchemy seja.
        send_fn: funkcija za pošiljanje (privzeto `send_backup_email`); injektirana
            zaradi testov.
        save_dir: če je podana, .sql zapišemo tudi v to mapo (lokalni test obnove).
        email: ali naj kopijo pošljemo po e-pošti.
        only: omeji na eno šolo (oznaka ali id) — uporabno za preizkus.

    Vrne seznam rezultatov: {school_id, slug, name, email, filename, path, bytes,
    tables, sent, saved, ok, message}.
    """
    send_fn = send_fn or send_backup_email

    query = db.query(School).order_by(School.id)
    if only not in (None, ""):
        if str(only).isdigit():
            query = query.filter(School.id == int(only))
        else:
            query = query.filter(School.slug == str(only))

    results: list[dict] = []
    for school in query.all():
        config = get_school_config(db, school.id)
        sql, tables = build_school_sql(db, school)
        filename = backup_filename(school)
        recipient = config.BACKUP_EMAIL or config.ADMIN_EMAIL
        size = len(sql.encode("utf-8"))

        saved_path = ""
        if save_dir:
            target_dir = Path(save_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            saved_path = str(target_dir / filename)
            Path(saved_path).write_text(sql, encoding="utf-8")

        sent: bool | None = None
        message = "Samo shranjeno (brez e-pošte)."
        if email:
            sent, message = send_fn(config, recipient, school, sql, filename)

        # Zagon je uspešen, če je bil vsak ZAHTEVAN korak uspešen.
        ok = (sent is not False) and (saved_path != "" or not save_dir)

        log_audit(
            db, None, "sistem:nočni-backup", "school_backup",
            f"school_id={school.id}, email={recipient or '-'}, file={filename}, "
            f"bytes={size}, sent={sent}, saved={saved_path or '-'}, nightly=True, tables={tables}",
            school_id=school.id,
        )
        results.append({
            "school_id": school.id,
            "slug": school.slug,
            "name": school.name,
            "email": recipient,
            "filename": filename,
            "path": saved_path,
            "bytes": size,
            "tables": tables,
            "sent": sent,
            "saved": bool(saved_path),
            "ok": ok,
            "message": message,
        })
    return results


def run(argv: list[str] | None = None) -> int:
    """Vrne 0, če je uspelo VSE; 1, če je katera koli kopija spodletela."""
    parser = argparse.ArgumentParser(
        prog="school_backups",
        description="Varnostna kopija (.sql) za vsako šolo posebej.",
    )
    parser.add_argument("--save", metavar="MAPA",
                        help="shrani .sql tudi v to mapo (za lokalni test obnove)")
    parser.add_argument("--no-email", action="store_true",
                        help="ne pošiljaj po e-pošti (samo shrani)")
    parser.add_argument("--school", metavar="OZNAKA_ALI_ID",
                        help="naredi kopijo samo za to šolo")
    args = parser.parse_args(list(argv or []))

    if args.no_email and not args.save:
        print("Ne delam nič: --no-email brez --save pomeni, da kopija nima cilja.")
        return 1

    if "postgresql" not in (os.getenv("DATABASE_URL") or ""):
        # Enako kot prej: brez PostgreSQL ni kaj izvažati (npr. lokalni razvoj).
        print("Preskočeno: DATABASE_URL ni PostgreSQL.")
        return 0

    db = SessionLocal()
    try:
        results = backup_all_schools(
            db,
            save_dir=args.save,
            email=not args.no_email,
            only=args.school,
        )
    finally:
        db.close()

    if not results:
        print("Ni najdenih šol — nič za narediti.")
        return 1 if args.school else 0

    failed = 0
    for r in results:
        rows = sum(r["tables"].values())
        if not r["ok"]:
            state = "NAPAKA"
        elif r["saved"] and r["sent"] is None:
            state = "SHRANJENO"
        else:
            state = "POSLANO"
        print(f"[{state}] {r['name']} ({r['slug']}): {r['filename']}, "
              f"{round(r['bytes'] / 1024, 1)} KB, {rows} vrstic"
              f"{' → ' + r['email'] if r['sent'] is not None and r['email'] else ''}"
              f"{' → ' + r['path'] if r['saved'] else ''}")
        if not r["ok"]:
            print(f"          razlog: {r['message']}")
            failed += 1

    print(f"Skupaj šol: {len(results)}, uspešnih: {len(results) - failed}, napak: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
