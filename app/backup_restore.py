# ─────────────────────────────────────────────────────────────────────────
# app/backup_restore.py — obnova podatkov iz .sql varnostne kopije
#
# Namen: šolski admin (in glavni admin) lahko naloži .sql varnostno kopijo
# (naša per-šolska kopija, format pg_dump plain) in obnovi podatke svoje šole:
#   - uporabniki  → users (računi šole, s gesli)
#   - nastavitve  → school_settings (RAZREDI, PROSTORI, URNIK, ŠTEVILA, MAIL…)
#   - dejavnosti  → activity_days + blocked_dates (dnevi dejavnosti)
#   - rezervacije → reservations
#   - ocenjevanje → assessments
#   - vse         → vse našteto (celotna šola, kot »ponovna postavitev«)
#
# Način delovanja (»revert«): za izbrana področja se IZBRIŠEJO vrstice TE ŠOLE
# in se znova vstavijo iz kopije. Vrstice drugih šol se ne dotaknemo — brisanje
# je vedno omejeno z `WHERE school_id = :sid`.
#
# ZAKAJ JE VRSTNI RED POMEMBEN: tabele kažejo na users (teacher_id,
# created_by_id) z NOT NULL omejitvami in BREZ ON DELETE CASCADE. Zato:
#   1. najprej izbrišemo PODATKE (rezervacije, ocenjevanja, blokade, dejavnosti),
#   2. šele nato uporabnike (pred tem sprostimo audit_log.user_id),
#   3. vstavljamo pa v obratnem vrstnem redu: uporabniki → nastavitve → podatki.
# Ob tem si zapomnimo preslikavo starih id-jev uporabnikov v nove (id_map), ker
# se id-ji v tabelah globalni (ena sekvenca za vse šole) in jih iz kopije ne
# vstavljamo. Brez preslikave bi rezervacije kazale na napačne (ali neobstoječe)
# učitelje.
#
# Zakaj lastni parser namesto `psql`? Nadzor nad tem, katere tabele in katere
# šole se dotaknemo, je eksplicitno v kodi — ne v rokah uporabnika. (psql je v
# sliki prisoten, a obnova tako ostane omejena na TE šole in znane tabele.)
# ─────────────────────────────────────────────────────────────────────────

import re
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

# Področja obnove → tabele, ki jih posamezno področje pokriva.
# Vrstni red v seznamu = vrstni red VSTAVLJANJA (uporabniki najprej!).
DOMAINS: dict[str, list[str]] = {
    "uporabniki": ["users"],
    "nastavitve": ["school_settings"],
    "dejavnosti": ["activity_days", "blocked_dates"],
    "rezervacije": ["reservations"],
    "ocenjevanje": ["assessments"],
    "vse": [
        "users",
        "school_settings",
        "activity_days",
        "blocked_dates",
        "reservations",
        "assessments",
    ],
}

DOMAIN_LABELS = {
    "uporabniki": "Uporabniki (računi šole, z gesli)",
    "nastavitve": "Nastavitve šole (razredi, prostori, urnik, števila)",
    "dejavnosti": "Dejavnosti (dnevi dejavnosti + zasedeni datumi)",
    "rezervacije": "Rezervacije prostorov",
    "ocenjevanje": "Ocenjevanja",
    "vse": "Vse (uporabniki, nastavitve, dejavnosti, rezervacije, ocenjevanja)",
}

# Vrstni red BRISANJA: podatki pred uporabniki (glej uvod).
_DELETE_ORDER = [
    "reservations",
    "assessments",
    "blocked_dates",
    "activity_days",
    "school_settings",
    "users",
]

# Tabele, ki imajo stolpce s sklicem na users.id (jih je treba preslikati).
_USER_FK_COLUMNS = {
    "reservations": ["teacher_id"],
    "assessments": ["teacher_id"],
    "blocked_dates": ["created_by_id"],
    "activity_days": ["created_by_id"],
}

# Nastavitve, ki jih pri obnovi PRESKOČIMO (v kopiji jih ni oz. so odvečne).
SKIPPED_SETTING_KEYS = {"STANJE_MAIL"}

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


def _delete_table(db: Session, school_id: int, table: str, users_of_school_sql) -> int:
    """Izbriši vrstice TE šole iz ene tabele. Pred brisanjem uporabnikov
    sprostimo audit_log.user_id (dnevnik ostane, sklic pa ne)."""
    if table == "users":
        db.execute(sql_text(
            f"UPDATE audit_log SET user_id = NULL WHERE user_id IN ({users_of_school_sql})"
        ), {"sid": school_id})
    return db.execute(
        sql_text(f"DELETE FROM {table} WHERE school_id = :sid"), {"sid": school_id}
    ).rowcount or 0


def _insert_table(
    db: Session,
    school_id: int,
    table: str,
    block: dict,
    *,
    id_map: dict[str, int] | None = None,
    fallback_user_id: int | None = None,
) -> dict:
    """Vstavi vrstice iz kopije v eno tabelo. Vrne povzetek za to tabelo."""
    current = _table_columns(db, table)
    meta = _table_meta(db, table)
    file_columns = block["columns"]
    has_school_col = _file_has_school_column(file_columns)

    # Uporabimo samo stolpce, ki obstajajo v obeh (kopija je lahko starejša
    # in nima npr. `termini` ali `school_id`). `id` izpustimo — glej uvod.
    use = [c for c in file_columns if c in current and c not in ("id", "school_id")]

    # Obvezni stolpci, ki jih v kopiji NI (starejša shema). Za bool/številke/
    # nize znamo varno zapolniti; za datum/JSON ne — takrat raje jasna napaka.
    required_missing = [
        c for c, m in meta.items()
        if c not in file_columns and c not in ("id", "school_id")
        and not m["nullable"] and m["default"] is None
    ]
    hard_missing = []
    fill: dict = {}
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
    fk_cols = [c for c in _USER_FK_COLUMNS.get(table, []) if c in current]

    params = []
    other = 0
    skipped_settings = 0
    fallback_used = 0
    for raw in block["rows"]:
        values = dict(zip(file_columns, [_unescape_copy_value(v) for v in raw]))
        if has_school_col:
            row_school = values.get("school_id")
            # Vrstice drugih šol v kopiji preskočimo (ne mešamo podatkov),
            # vrstice brez šole (starejše kopije) štejemo k tej šoli.
            if row_school not in (None, "", str(school_id)):
                other += 1
                continue
        # Odvečne nastavitve (npr. STANJE_MAIL) preskočimo.
        if table == "school_settings" and (values.get("key") or "") in SKIPPED_SETTING_KEYS:
            skipped_settings += 1
            continue
        row = {c: values.get(c) for c in use}
        row.update(fill)

        # Sklici na uporabnike: preslikaj stare id-je v nove.
        for col in fk_cols:
            old = row.get(col)
            if old in (None, ""):
                continue
            new_id = (id_map or {}).get(str(old))
            if new_id is None and str(old).lstrip("-").isdigit() and id_map:
                # Sklica v kopiji ni med uporabniki. Če ta id v bazi VSEENO
                # obstaja (npr. uporabnik druge šole), ga obdržimo — tuji ključ
                # je s tem veljaven; sicer uporabimo rezervo (admin, ki obnavlja).
                exists = db.execute(
                    sql_text("SELECT 1 FROM users WHERE id = :uid"), {"uid": int(old)}
                ).first()
                if exists:
                    new_id = int(old)
            if new_id is None and meta.get(col, {}).get("nullable"):
                row[col] = None
            elif new_id is None:
                fallback_used += 1
                row[col] = fallback_user_id
            else:
                row[col] = new_id

        if include_school:
            row["school_id"] = school_id
        params.append(row)

    insert_cols = use + sorted(fill.keys()) + (["school_id"] if include_school else [])
    inserted = 0
    if params:
        db.execute(
            sql_text(
                f"INSERT INTO {table} ({', '.join(insert_cols)}) "
                f"VALUES ({', '.join(':' + c for c in insert_cols)})"
            ),
            params,
        )
        inserted = len(params)

    return {
        "inserted": inserted,
        "columns": use,
        "from_file": len(block["rows"]),
        "other_schools": other,
        "skipped_settings": skipped_settings,
        "fallback_used": fallback_used,
        "filled": sorted(fill.keys()) if required_missing else [],
    }


def _build_user_id_map(db: Session, school_id: int, users_block: dict) -> dict[str, int]:
    """Sestavi preslikavo STARI id (iz kopije) → NOVI id (v bazi).

    Id-jev iz kopije ne vstavljamo (so globalni in lahko trčijo z drugo šolo),
    zato vrstice povežemo po uporabniškem imenu, ki je v šoli unikatno:
    iz kopije preberemo (stari id, uporabniško ime), v bazi pa poiščemo novi id
    istega uporabniškega imena.
    """
    rows = db.execute(sql_text(
        "SELECT id, username FROM users WHERE school_id = :sid"
    ), {"sid": school_id}).fetchall()
    by_username = {str(r[1]).lower(): r[0] for r in rows}

    columns = users_block["columns"]
    if "id" not in columns or "username" not in columns:
        return {}
    id_idx = columns.index("id")
    uname_idx = columns.index("username")

    mapping: dict[str, int] = {}
    for raw in users_block["rows"]:
        old_id = _unescape_copy_value(raw[id_idx]) if id_idx < len(raw) else None
        uname = _unescape_copy_value(raw[uname_idx]) if uname_idx < len(raw) else None
        new_id = by_username.get(str(uname).lower()) if uname else None
        if old_id not in (None, "") and new_id is not None:
            mapping[str(old_id)] = new_id
    return mapping


def restore_domain(
    db: Session,
    school_id: int,
    sql_text_input: str,
    domain: str,
    fallback_user_id: int | None = None,
) -> dict:
    """Obnovi izbrano področje podatkov te šole iz .sql kopije.

    `fallback_user_id` je uporabnik, ki obnovitev izvaja — uporabimo ga, kadar
    kopija vsebuje sklic na uporabnika, ki ga v kopiji ni (npr. glavni admin pri
    starih rezervacijah), stolpec pa je NOT NULL.

    Vrne povzetek: {'domain', 'label', 'tables': {tabela: {...}}, 'missing',
    'skipped_other_schools', 'id_map_size', 'warnings'}
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

    tables = DOMAINS[domain]
    summary = {
        "domain": domain,
        "label": DOMAIN_LABELS.get(domain, domain),
        "tables": {},
        "missing": [],
        "skipped_other_schools": 0,
        "id_map_size": 0,
        "warnings": [],
    }

    present = [t for t in tables if t in blocks]
    summary["missing"] = [t for t in tables if t not in blocks]
    if not present:
        raise HTTPException(
            status_code=400,
            detail="V kopiji ni nobene od tabel za izbrano področje.",
        )

    users_of_school_sql = "SELECT id FROM users WHERE school_id = :sid"

    # Rezervni uporabnik za sklice, ki jih v kopiji ni (npr. rezervacija, ki jo je
    # ustvaril uporabnik, ki ga v kopiji ni): najprej admin, ki obnavlja, sicer
    # glavni (najstarejši) admin te šole.
    effective_fallback = fallback_user_id
    if effective_fallback is None:
        from app.tenancy import primary_admin
        admin = primary_admin(db, school_id)
        effective_fallback = admin.id if admin is not None else None

    # ── 1. FAZA BRISANJA: podatki → nastavitve → uporabniki ─────────────
    for table in _DELETE_ORDER:
        if table not in present:
            continue
        summary["tables"].setdefault(table, {})["deleted"] = _delete_table(
            db, school_id, table, users_of_school_sql
        )

    # ── 2. FAZA VSTAVLJANJA: uporabniki → nastavitve → podatki ──────────
    id_map: dict[str, int] = {}
    if "users" in present:
        result = _insert_table(db, school_id, "users", blocks["users"])
        db.flush()
        id_map = _build_user_id_map(db, school_id, blocks["users"])
        summary["id_map_size"] = len(id_map)
        summary["tables"]["users"].update(result)

    for table in present:
        if table == "users":
            continue
        result = _insert_table(
            db, school_id, table, blocks[table],
            id_map=id_map,
            fallback_user_id=effective_fallback,
        )
        summary["tables"][table].update(result)
        summary["skipped_other_schools"] += result["other_schools"]

    # Vsa povzetek polja morajo obstajati tudi za tabele, ki so bile samo izbrisane.
    for table, info in summary["tables"].items():
        info.setdefault("inserted", 0)
        info.setdefault("from_file", 0)
        info.setdefault("deleted", 0)

    # Združljivost s starejšo obliko povzetka (UI/testi): polja, ki jih je bilo
    # treba zapolniti, ker jih kopija ni imela.
    filled = {t: v["filled"] for t, v in summary["tables"].items() if v.get("filled")}
    if filled:
        summary["filled_columns"] = filled

    fallbacks = sum(v.get("fallback_used", 0) for v in summary["tables"].values())
    summary["fallback_used"] = fallbacks
    if fallbacks:
        summary["warnings"].append(
            f"Pri {fallbacks} vrsticah sklic na uporabnika ni bil v kopiji — "
            f"uporabljen je admin, ki obnavlja."
        )

    return summary
