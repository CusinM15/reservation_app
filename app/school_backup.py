# ─────────────────────────────────────────────────────────────────────────
# app/school_backup.py — varnostna kopija (.sql) SAMO za eno šolo + pošiljanje
#
# Namen: šolski admin (in glavni admin) na /settings klikne »Naredi backup«.
# Aplikacija sestavi .sql izpis podatkov TE ŠOLE in ga pošlje po e-pošti na
# naslov za varnostne kopije (BACKUP_EMAIL, sicer ADMIN_EMAIL).
#
# Zakaj lasten izvoz namesto `pg_dump`? V kontejnerju ni psql/pg_dump
# odjemalca. Izpis je namerno v obliki `pg_dump -F p` (COPY bloki), ker jo zna
# prebrati naš obstoječi obnovitveni parser (app/backup_restore.py) — kopijo je
# torej mogoče obnoviti kar prek strani /settings → »Obnova iz varnostne kopije«.
#
# Varnost: vsaka poizvedba je omejena na school_id TE šole (tabela `schools` po
# `id`), zato datoteka NE vsebuje podatkov drugih šol.
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import smtplib
import ssl
from datetime import date, datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

# Tabele v kopiji šole. Vrstni red = vrstni red izpisa (najprej šola in njene
# nastavitve, nato uporabniki in njihovi podatki).
BACKUP_TABLES = [
    "schools",
    "school_settings",
    "school_aliases",
    "users",
    "activity_days",
    "blocked_dates",
    "reservations",
    "assessments",
]


def _columns(db: Session, table: str) -> list[str]:
    """Stolpci tabele po vrstnem redu (kot jih pozna baza)."""
    rows = db.execute(sql_text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t ORDER BY ordinal_position"
    ), {"t": table}).fetchall()
    return [r[0] for r in rows]


def _copy_value(value) -> str:
    """Pretvori vrednost v obliko COPY (pg_dump text).

    Pravila: NULL → \\N, bool → t/f, JSON → besedilo, datum/čas → ISO,
    tab → \\t, nova vrstica → \\n, backslash → \\\\ (najprej!).
    """
    if value is None:
        return r"\N"
    if isinstance(value, bool):
        return "t" if value else "f"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    elif isinstance(value, datetime):
        value = value.isoformat(sep=" ")
    elif isinstance(value, date):
        value = value.isoformat()
    else:
        value = str(value)
    return (value.replace("\\", "\\\\").replace("\t", "\\t")
                 .replace("\n", "\\n").replace("\r", "\\r"))


def build_school_sql(db: Session, school) -> tuple[str, dict]:
    """Sestavi .sql izpis podatkov ENE šole.

    Vrne (sql, povzetek) kjer je povzetek {tabela: število vrstic}.
    """
    sid = int(school.id)
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "-- ─────────────────────────────────────────────────────────────",
        "-- Varnostna kopija šole (samo podatki te šole)",
        f"-- Šola:        {school.name} (oznaka: {school.slug}, school_id={sid})",
        f"-- Ustvarjeno:  {generated} UTC",
        "-- Vsebuje IZKLJUČNO podatke te šole — vrstic drugih šol NI.",
        "-- Obnovitev:   /settings → »Obnova iz varnostne kopije«",
        "-- ─────────────────────────────────────────────────────────────",
        "",
        "BEGIN;",
        "",
    ]
    summary: dict[str, int] = {}
    for table in BACKUP_TABLES:
        cols = _columns(db, table)
        if not cols:
            continue
        if table == "schools":
            where = "id = :sid"
        elif "school_id" in cols:
            where = "school_id = :sid"
        else:
            # Tabela brez school_id (npr. globalna) — v kopijo šole ne sodi.
            continue
        rows = db.execute(
            sql_text(f"SELECT {', '.join(cols)} FROM {table} WHERE {where}"), {"sid": sid}
        ).fetchall()
        lines.append("--")
        lines.append(f"-- Podatki: {table} ({len(rows)} vrstic)")
        lines.append("--")
        lines.append(f"COPY public.{table} ({', '.join(cols)}) FROM stdin;")
        for row in rows:
            lines.append("\t".join(_copy_value(v) for v in row))
        lines.append("\\.")
        lines.append("")
        summary[table] = len(rows)
    lines.append("COMMIT;")
    lines.append("")
    return "\n".join(lines), summary


def backup_filename(school) -> str:
    """Ime datoteke: sola-backup-<oznaka>-<datum>.sql"""
    return f"sola-backup-{school.slug}-{datetime.utcnow():%Y-%m-%d}.sql"


def send_backup_email(config, to_email: str, school, sql: str, filename: str) -> tuple[bool, str]:
    """Pošlji kopijo kot priponko po e-pošti. Vrne (poslano, sporočilo).

    Zakaj ne obstoječi `_send_email`? Ta pošilja samo navadno besedilo (brez
    priponk) in napake tiho požre — tu pa uporabnik MORA izvedeti, ali je
    pošiljanje uspelo.
    """
    if not to_email:
        return False, "Naslov za varnostne kopije ni nastavljen (BACKUP_EMAIL oz. ADMIN_EMAIL)."
    if not config.MAIL_PASSWORD:
        return False, "SMTP geslo ni nastavljeno — pošiljanje ni mogoče."

    msg = MIMEMultipart()
    msg["Subject"] = f"Varnostna kopija šole {school.name} — {datetime.utcnow():%d. %m. %Y}"
    msg["From"] = config.MAIL_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(
        f"V priponki je varnostna kopija (.sql) podatkov šole {school.name}.\n"
        f"Datoteka vsebuje izključno podatke te šole.\n"
        f"Obnovitev: nastavitve šole → »Obnova iz varnostne kopije«.\n",
        "plain", "utf-8",
    ))
    part = MIMEApplication(sql.encode("utf-8"), _subtype="sql")
    part.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(part)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(config.MAIL_SERVER, config.MAIL_PORT) as s:
            s.starttls(context=context)
            s.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
            s.send_message(msg)
    except Exception as exc:                      # noqa: BLE001 — sporočimo napako uporabniku
        return False, f"Pošiljanje ni uspelo: {exc}"
    return True, f"Kopija poslana na {to_email}."
