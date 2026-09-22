# ─────────────────────────────────────────────────────────────────────────
# app/backup_restore.py — obnova podatkov iz .sql varnostne kopije
#
# Namen: šolski admin (in glavni admin) lahko naloži .sql varnostno kopijo
# (pg_dump) in obnovi posamezno področje podatkov svoje šole:
#   - dejavnosti   → activity_days + blocked_dates (dnevi dejavnosti)
#   - rezervacije  → reservations
#   - ocenjevanje  → assessments
#   - vse          → vse našteto
#
# Način delovanja (»revert«): za izbrane tabele se IZBRIŠEJO vrstice TE ŠOLE
# in se znova vstavijo iz kopije. Vrstice drugih šol se ne dotaknemo —
# brisanje je vedno omejeno z `WHERE school_id = :sid`.
#
# Zakaj se `id` ne ohrani? Ker so id-ji v tabelah globalni (ena sekvenca za
# vse šole). Če bi vstavili stare id-je, bi se lahko zaleteli v vrstico druge
# šole (isti id). Zato id prepustimo bazi, vsebina pa je identična kopiji.
# Tuji ključi (teacher_id, created_by_id) se ohranijo, ker kažejo na users,
# ki jih obnova ne spreminja.
#
# Zakaj vlastni parser namesto `psql`? Aplikacija teče v kontejnerju brez
# psql odjemalca, pa tudi nadzor nad tem, katere tabele in katere šole se
# dotaknemo, je tako eksplicitno v kodi — ne v rokah uporabnika.
# ─────────────────────────────────────────────────────────────────────────

import re
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

# Področja obnove → tabele, ki jih posamezno področje pokriva.
DOMAINS: dict[str, list[str]] = {
    "dejavnosti": ["activity_days", "blocked_dates"],
    "rezervacije": ["reservations"],
    "ocenjevanje": ["assessments"],
    "vse": ["activity_days", "blocked_dates", "reservations", "assessments"],
}

DOMAIN_LABELS = {
    "dejavnosti": "Dejavnosti (dnevi dejavnosti + zasedeni datumi)",
    "rezervacije": "Rezervacije prostorov",
    "ocenjevanje": "Ocenjevanja",
    "vse": "Vse (dejavnosti, rezervacije, ocenjevanja)",
}

# COPY public.<table> (col1, col2, ...) FROM stdin;
_COPY_RE = re.compile(
    r"^COPY\s+(?:public\.)?\"?([A-Za-z_][A-Za-z0-9_]*)\"?\s*\(([^)]*)\)\s+FROM\s+stdin;",
    re.IGNORECASE,
)
_INSERT_RE = re.compile(
    r"^INSERT\s+INTO\s+(?:public\.)?\"?([A-Za-z_][A-Za-z0-9_]*)\"?\s*[\(;]", re.IGNORECASE
)

# Vrstni red je pomemben: najprej `\\` (escape za backslash), nato ostalo.
_UNESCAPE = {"\\": "\\", "t": "\t", "n": "\n", "r": "\r", "b": "\b", "f": "\f", "v": "\v"}
_UNESCAPE_RE = re.compile(r"\\(.)")


def _unescape_copy_value(value: str):
    """Razreši escape zaporedja formata COPY (in \\N → NULL)."""
    if value == r"\N":
        return None
    return _UNESCAPE_RE.sub(lambda m: _UNESCAPE.get(m.group(1), m.group(1)), value)


def parse_copy_blocks(sql: str) -> dict:
    """Razreži pg_dump (plain) besedilo na tabele: {tabela: {columns, rows}}.

    Podprta je oblika, ki jo uporablja `pg_dump -F p` (privzeto): zaporedje
    `COPY ... FROM stdin;`, podatkovne vrstice (tab-ločene), zaključek `\\.`.
    """
    blocks: dict[str, dict] = {}
    lines = (sql or "").splitlines()
    i = 0
    while i < len(lines):
        match = _COPY_RE.match(lines[i].strip())
        if not match:
            i += 1
            continue
        table = match.group(1).lower()
        columns = [c.strip().strip('"') for c in match.group(2).split(",") if c.strip()]
        rows = []
        i += 1
        while i < len(lines) and lines[i].strip() != r"\.":
            line = lines[i]
            if line.strip() != "":
                rows.append(line.split("\t"))
            i += 1
        blocks[table] = {"columns": columns, "rows": rows}
        i += 1
    return blocks


def _table_columns(db: Session, table: str) -> list[str]:
    """Vrni stolpce tabele iz baze (po vrstnem redu)."""
    rows = db.execute(sql_text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t ORDER BY ordinal_position"
    ), {"t": table}).fetchall()
    return [r[0] for r in rows]


def _table_meta(db: Session, table: str) -> dict:
    """Metapodatki stolpcev: tip, ali je NULL dovoljen, privzeta vrednost."""
    rows = db.execute(sql_text(
        "SELECT column_name, data_type, is_nullable, column_default "
        "FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t ORDER BY ordinal_position"
    ), {"t": table}).fetchall()
    return {r[0]: {"type": (r[1] or "").lower(), "nullable": r[2] == "YES",
                   "default": r[3]} for r in rows}


# Vrednosti, s katerimi lahko zapolnimo stolpec, ki je v trenutni shemi
# OBVEZEN, a ga kopija (starejša shema) ne vsebuje.
_FALLBACK_BY_TYPE = {
    "boolean": False,
    "smallint": 0, "integer": 0, "bigint": 0,
    "numeric": 0, "real": 0, "double precision": 0,
    "character varying": "", "character": "", "text": "",
}

# Časovne oznake (created_at/updated_at) so evidenca, ne vsebina — če jih
# starejša kopija nima, jih zapolnimo s trenutnim časom, namesto da bi
# obnovitev spodletela. Datumi, ki NOSIJO pomen (npr. reservations.date,
# blocked_dates.date), pa ostajajo strogi: tam raje jasna napaka.
_BOOKKEEPING_TIMESTAMP_SUFFIX = "_at"


def _file_has_school_column(columns: list[str]) -> bool:
    return "school_id" in [c.lower() for c in columns]


def restore_domain(db: Session, school_id: int, sql_text_input: str, domain: str) -> dict:
    """Obnovi izbrano področje podatkov te šole iz .sql kopije.

    Vrne povzetek: {'domain', 'tables': {tabela: {deleted, inserted, columns}},
    'missing': [...], 'skipped_other_schools': int}
    """
    if domain not in DOMAINS:
        raise HTTPException(status_code=400, detail=f"Neznano področje: {domain}")

    if _INSERT_RE.search(sql_text_input or "") and not _COPY_RE.search(sql_text_input or ""):
        raise HTTPException(
            status_code=400,
            detail="V datoteki so INSERT stavki. Podprta je oblika pg_dump COPY "
                   "(privzeti izpis `pg_dump -F p`).",
        )

    blocks = parse_copy_blocks(sql_text_input)
    if not blocks:
        raise HTTPException(
            status_code=400,
            detail="V datoteki ni prepoznanih podatkov (pričakujem pg_dump obliki COPY).",
        )

    summary = {
        "domain": domain,
        "label": DOMAIN_LABELS.get(domain, domain),
        "tables": {},
        "missing": [],
        "skipped_other_schools": 0,
    }

    for table in DOMAINS[domain]:
        block = blocks.get(table)
        if block is None:
            summary["missing"].append(table)
            continue

        current = _table_columns(db, table)
        meta = _table_meta(db, table)
        file_columns = block["columns"]
        has_school_col = _file_has_school_column(file_columns)

        # Uporabimo samo stolpce, ki obstajajo v obeh (kopija je lahko starejša
        # in nima npr. `termini` ali `school_id`). `id` izpustimo — glej uvod.
        use = [
            c for c in file_columns
            if c in current and c not in ("id", "school_id")
        ]

        # Obvezni stolpci, ki jih v kopiji NI (starejša shema). Za bool/številke/
        # nize znamo varno zapolniti; za datum/JSON ne — takrat raje jasna napaka,
        # kot da bi si izmislili podatke.
        required_missing = [
            c for c, m in meta.items()
            if c not in file_columns and c not in ("id", "school_id")
            and not m["nullable"] and m["default"] is None
        ]
        hard_missing = []
        fill = {}
        for c in required_missing:
            data_type = meta[c]["type"]
            if data_type in _FALLBACK_BY_TYPE:
                fill[c] = _FALLBACK_BY_TYPE[data_type]
            elif data_type.startswith("timestamp") and c.endswith(_BOOKKEEPING_TIMESTAMP_SUFFIX):
                fill[c] = datetime.utcnow()
            else:
                hard_missing.append(c)
        if hard_missing:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"V kopiji manjkajo obvezni stolpci za tabelo {table}: "
                    f"{', '.join(hard_missing)}. Kopija je očitno iz starejše sheme — "
                    f"obnovitev s to datoteko ni mogoča za to področje."
                ),
            )

        include_school = "school_id" in current

        deleted = db.execute(
            sql_text(f"DELETE FROM {table} WHERE school_id = :sid"), {"sid": school_id}
        ).rowcount or 0

        inserted = 0
        if use or fill:
            insert_cols = use + sorted(fill.keys()) + (["school_id"] if include_school else [])
            insert_sql = sql_text(
                f"INSERT INTO {table} ({', '.join(insert_cols)}) "
                f"VALUES ({', '.join(':' + c for c in insert_cols)})"
            )
            params = []
            other = 0
            for raw in block["rows"]:
                values = dict(zip(file_columns, [_unescape_copy_value(v) for v in raw]))
                if has_school_col:
                    row_school = values.get("school_id")
                    # Vrstice drugih šol v kopiji preskočimo (ne mešamo podatkov),
                    # vrstice brez šole (starejše kopije) štejemo k tej šoli.
                    if row_school not in (None, "", str(school_id)):
                        other += 1
                        continue
                row = {c: values.get(c) for c in use}
                row.update(fill)
                if include_school:
                    row["school_id"] = school_id
                params.append(row)
            if params:
                db.execute(insert_sql, params)
                inserted = len(params)
            summary["skipped_other_schools"] += other
            if required_missing:
                summary.setdefault("filled_columns", {})[table] = sorted(fill.keys())

        summary["tables"][table] = {
            "deleted": deleted,
            "inserted": inserted,
            "columns": use,
            "from_file": len(block["rows"]),
        }

    return summary