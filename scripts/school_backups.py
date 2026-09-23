#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────
# scripts/school_backups.py — NOČNI backup: za VSAKO šolo svoja kopija
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
#   python -m scripts.school_backups          # pošlje po e-pošti
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

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


def backup_all_schools(db, send_fn=None) -> list[dict]:
    """Za vsako šolo sestavi .sql (samo njeni podatki) in jo pošlje po e-pošti.

    `send_fn` je injektiran zaradi testov (privzeto `send_backup_email`).
    Vrne seznam rezultatov: {school_id, slug, name, email, filename, bytes,
    tables, sent, message}.
    """
    send_fn = send_fn or send_backup_email
    results: list[dict] = []

    for school in db.query(School).order_by(School.id).all():
        config = get_school_config(db, school.id)
        sql, tables = build_school_sql(db, school)
        filename = backup_filename(school)
        recipient = config.BACKUP_EMAIL or config.ADMIN_EMAIL
        size = len(sql.encode("utf-8"))

        sent, message = send_fn(config, recipient, school, sql, filename)

        log_audit(
            db, None, "sistem:nočni-backup", "school_backup",
            f"school_id={school.id}, email={recipient or '-'}, file={filename}, "
            f"bytes={size}, sent={sent}, nightly=True, tables={tables}",
            school_id=school.id,
        )
        results.append({
            "school_id": school.id,
            "slug": school.slug,
            "name": school.name,
            "email": recipient,
            "filename": filename,
            "bytes": size,
            "tables": tables,
            "sent": sent,
            "message": message,
        })
    return results


def run() -> int:
    """Vrne 0, če je uspelo VSE; 1, če je katera koli kopija spodletela."""
    if "postgresql" not in (os.getenv("DATABASE_URL") or ""):
        # Enako kot prej: brez PostgreSQL ni kaj izvažati (npr. lokalni razvoj).
        print("Preskočeno: DATABASE_URL ni PostgreSQL.")
        return 0

    db = SessionLocal()
    try:
        results = backup_all_schools(db)
    finally:
        db.close()

    if not results:
        print("V bazi ni šol — nič za narediti.")
        return 0

    failed = 0
    for r in results:
        rows = sum(r["tables"].values())
        state = "POSLANO" if r["sent"] else "NAPAKA"
        print(f"[{state}] {r['name']} ({r['slug']}): {r['filename']}, "
              f"{round(r['bytes'] / 1024, 1)} KB, {rows} vrstic → {r['email'] or '-'}")
        if not r["sent"]:
            print(f"          razlog: {r['message']}")
            failed += 1

    print(f"Skupaj šol: {len(results)}, poslanih: {len(results) - failed}, napak: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
