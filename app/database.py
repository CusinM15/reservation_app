# ─────────────────────────────────────────────────────────────────────────
# app/database.py — Povezava s podatkovno bazo in upravljanje sej
#
# Namen: Ustvari SQLAlchemy engine, definira SessionLocal za delo z
# bazo ter nudi pomožne funkcije: get_db (FastAPI dependency), init_db
# (inicializacija tabel in migracij) ter log_audit (beleženje dogodkov).
#
# Zakaj lastna implementacija namesto Alembic migracij?
# Aplikacija je majhna in ima stabilno shemo. Namesto polnega migracijskega
# ogrodja uporabljamo idempotentne ALTER TABLE stavke v init_db(), ki so
# dovolj za redke spremembe sheme.
# ─────────────────────────────────────────────────────────────────────────

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, declarative_base, Session

import os
from app.config import settings

# ── Engine ────────────────────────────────────────────────────────────
# Velikost sklada povezav in preverjanje »mrtvih« povezav.
# Zakaj? Gostujoče baze (Railway, Heroku, upravljani PostgreSQL) stojijo za
# proxyjem, ki tiho zapre povezave, ki nekaj časa mirujejo. Brez preverjanja
# (pool_pre_ping) in obnavljanja (pool_recycle) prva zahteva po mirovanju
# čaka na ponovno vzpostavitev povezave (ali pade) — uporabniku se to vidi kot
# »včasih se stran nalaga več sekund«. Vrednosti so nastavljive z okoljem.
def create_db_engine():
    """Produkcijski engine s skladom povezav (velikost + mrtve povezave).

    Uporablja ga modul sam (engine = create_db_engine()) in test_performance,
    ki mora preveriti PRAVO produkcijsko konfiguracijo — testi sicer (conftest)
    engine nadomestijo z NullPool za izolacijo med testi.
    """
    return create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "300")),
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        connect_args={},
    )


engine = create_db_engine()

# ── SessionLocal ──────────────────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── Base ──────────────────────────────────────────────────────────────
Base = declarative_base()


def get_db():
    """FastAPI dependency, ki ustvari in zapre DB sejo."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def db_connection_hint(url: str | None = None) -> str:
    """Razumljivo sporočilo, ko se aplikacija ne more povezati na bazo.

    Zakaj? Na hosting ponudnikih (Railway, Heroku) najpogostejša napaka ni v
    kodi: v DATABASE_URL ostane VZOREC iz navodil (gostitelj dobesedno »host«)
    ali pa na spremenljivko sploh ni povezana baza. Takrat psycopg2 javi le
    »could not translate host name "host"«, kar uporabniku nič ne pove.
    """
    from urllib.parse import urlparse

    try:
        host = (urlparse(url or "").hostname or "").strip().lower()
    except Exception:                       # pokvarjen URL — tudi to pojasnimo
        host = ""

    hint = ""
    if host in ("host", "h", "example.com", "dbname"):
        hint = (f"V DATABASE_URL je ostal VZOREC (gostitelj »{host}«). "
                "Vnesi pravi naslov baze.")
    elif host in ("localhost", "127.0.0.1", "::1"):
        hint = (f"DATABASE_URL kaže na »{host}«, torej na isti strežnik. "
                "V gostovanju (Railway, Docker) mora kazati na ime storitve baze.")
    elif not host:
        hint = "V DATABASE_URL ni naslova baze (manjka ime gostitelja)."

    if not hint:
        hint = f"DATABASE_URL je nastavljen, a povezava na gostitelja »{host}« ni uspela."

    return (f"{hint} "
            "Na Railwayu: Variables → Add Reference → izberi storitev Postgres → "
            "DATABASE_URL (tako se vrednost poveže samodejno; ročnega vpisa ne "
            "potrebuješ). Enako preveri, da SECRET_KEY ni vzorec iz navodil.")


def init_db():
    """Ustvari vse tabele in izvede lahke idempotentne migracije.

    Trenutne migracije:
    - series_id v reservations: serijske rezervacije
    - name v reservations: ime serijske rezervacije
    - activity_days: nova tabela za UI "Vnos dejavnosti" (source=xlsx/manual)
    """
    import app.models  # noqa: F401 – ensure models are registered

    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError as exc:
        # Povezava na bazo ni uspela — javi ČLOVEŠKO razlago (in ne le
        # psycopg2 sledi), ker je to najpogostejša napaka pri postavitvi.
        from app.config import settings
        raise RuntimeError(db_connection_hint(settings.DATABASE_URL)) from exc

    def _migrate(statement: str) -> None:
        try:
            with engine.begin() as conn:
                conn.execute(text(statement))
        except Exception:
            pass  # Že obstaja / že izvedeno — to je OK

    def _migrate_autocommit(statement: str) -> None:
        """Za stavke, ki se ne smejo izvajati v transakciji (ALTER TYPE ...).

        PostgreSQL zahteva, da ALTER TYPE ... ADD VALUE teče zunaj
        transakcijskega bloka — zato uporabimo AUTOCOMMIT povezavo.
        """
        try:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text(statement))
        except Exception:
            pass

    # ── Reservacije ─────────────────────────────────────────────────────
    _migrate("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS series_id VARCHAR")
    _migrate("CREATE INDEX IF NOT EXISTS ix_reservations_series_id ON reservations (series_id)")
    _migrate("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS name VARCHAR")

    # ── Govorilne prijave ───────────────────────────────
    # opis: kratek opis starša (zakaj se prijavlja) ob najavi na govorilne.
    _migrate("ALTER TABLE govorilne_prijave ADD COLUMN IF NOT EXISTS opis VARCHAR DEFAULT ''")
    # ima_govorilne: kljukica pri uporabniku — govorilne ure (članstvo od 30.10.2026)
    _migrate("ALTER TABLE users ADD COLUMN IF NOT EXISTS ima_govorilne BOOLEAN NOT NULL DEFAULT FALSE")

    # ── Nova tabela: activity_days (UI "Vnos dejavnosti") ──────────────
    _migrate(
        "CREATE TABLE IF NOT EXISTS activity_days ("
        "id SERIAL PRIMARY KEY,"
        "grade VARCHAR NOT NULL,"
        "section VARCHAR NOT NULL,"
        "title VARCHAR NOT NULL DEFAULT '',"
        "subtitle VARCHAR DEFAULT '',"
        "full_day BOOLEAN NOT NULL DEFAULT FALSE,"
        "recurring BOOLEAN NOT NULL DEFAULT FALSE,"
        "date_from DATE,"
        "date_to DATE,"
        "date_undetermined BOOLEAN NOT NULL DEFAULT FALSE,"
        "date_text VARCHAR DEFAULT '',"
        "all_classes BOOLEAN NOT NULL DEFAULT FALSE,"
        "classes TEXT DEFAULT '',"
        "prostori TEXT DEFAULT '',"
        "cena VARCHAR DEFAULT '',"
        "vodja VARCHAR DEFAULT '',"
        "opomba TEXT DEFAULT '',"
        "created_by_id INTEGER REFERENCES users(id),"
        "created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),"
        "updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),"
        "source VARCHAR NOT NULL DEFAULT 'manual'"
        ")"
    )
    _migrate("CREATE INDEX IF NOT EXISTS ix_activity_days_grade ON activity_days (grade)")
    _migrate("CREATE INDEX IF NOT EXISTS ix_activity_days_section ON activity_days (section)")
    _migrate("ALTER TABLE activity_days ADD COLUMN IF NOT EXISTS source VARCHAR NOT NULL DEFAULT 'manual'")
    _migrate("CREATE INDEX IF NOT EXISTS ix_activity_days_source ON activity_days (source)")
    # parent_title: združevanje poddejavnosti pod glavni naslov (npr. TEHNIŠKI DAN)
    _migrate("ALTER TABLE activity_days ADD COLUMN IF NOT EXISTS parent_title VARCHAR")
    _migrate("CREATE INDEX IF NOT EXISTS ix_activity_days_parent_title ON activity_days (parent_title)")
        # termini
    _migrate("ALTER TABLE activity_days ADD COLUMN IF NOT EXISTS termini JSONB")

    # ── Večšolska (multi-tenant) prenova ────────────────────────────────
    # 0) Nova vloga main_admin (glavni admin, vidi vse šole). Vloga je v
    #    PostgreSQL naravni ENUM tip 'roleenum' — dodati ji moramo vrednost.
    #    ALTER TYPE ... ADD VALUE mora teči zunaj transakcije.
    _migrate_autocommit("ALTER TYPE roleenum ADD VALUE IF NOT EXISTS 'main_admin'")

    # Tabele schools / school_aliases / school_settings ustvari
    # Base.metadata.create_all (modeli so registrirani zgoraj). Tu samo
    # dodamo school_id na obstoječe tabele in uredimo indekse.
    #
    # Zakaj school_id na vsaki tabeli? To je meja izolacije: vsaka
    # poizvedba šolskega uporabnika se filtrira po njegovi šoli.
    for _table in (
        "reservations",
        "assessments",
        "blocked_dates",
        "activity_days",
        "audit_log",
        "users",
    ):
        _migrate(
            f"ALTER TABLE {_table} ADD COLUMN IF NOT EXISTS school_id INTEGER REFERENCES schools(id)"
        )
        _migrate(
            f"CREATE INDEX IF NOT EXISTS ix_{_table}_school_id ON {_table} (school_id)"
        )

    # Unikatnost uporabniškega imena/e-pošte je od zdaj ZNOTRAJ šole, ne
    # globalna (dve šoli lahko imata vsaka svojega "jnovak").
    # Vrstni red: najprej ustvari sestavljena unikatna indeksa, šele nato
    # sprosti globalna — če sestavljeni indeks ne uspe (npr. podvojeni
    # podatki), globalna unikatnost ostane in nič se ne pokvari.
    _migrate("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_school_username ON users (school_id, username)")
    _migrate("DROP INDEX IF EXISTS ix_users_username")
    _migrate("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)")
    _migrate("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_school_email ON users (school_id, email)")
    _migrate("DROP INDEX IF EXISTS ix_users_email")
    _migrate("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")


def log_audit(db: Session, user_id: int, user_name: str, action: str,
              entity_type: str, entity_id: int | None = None,
              details: str | None = None) -> None:
    """Zapiši dogodek v audit_log tabelo. Kličeš pred commitom."""
    from app.models import AuditLog
    log = AuditLog(
        user_id=user_id,
        user_name=user_name,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.add(log)