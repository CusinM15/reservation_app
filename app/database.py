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
from sqlalchemy.orm import sessionmaker, declarative_base, Session

import os
from app.config import settings

# ── Engine ────────────────────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={},
)

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


def init_db():
    """Ustvari vse tabele in izvede lahke idempotentne migracije.

    Trenutne migracije:
    - series_id v reservations: serijske rezervacije
    - name v reservations: ime serijske rezervacije
    - activity_days: nova tabela za UI "Vnos dejavnosti" (source=xlsx/manual)
    """
    import app.models  # noqa: F401 – ensure models are registered

    Base.metadata.create_all(bind=engine)

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