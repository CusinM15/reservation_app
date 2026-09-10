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
# Ustvari SQLAlchemy engine iz DATABASE_URL. Aplikacija je 100%
# PostgreSQL — SQLite ni podprt nikjer (ne v produkciji, ne lokalno).
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={},
)

# ── SessionLocal ──────────────────────────────────────────────────────
# Tovarna za ustvarjanje sej. autocommit=False pomeni, da moramo
# eksplicitno klicati commit() — to je standardni SQLAlchemy 2.0 vzorec.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── Base ──────────────────────────────────────────────────────────────
# Deklarativni base za SQLAlchemy modele.
Base = declarative_base()


def get_db():
    """FastAPI dependency, ki ustvari in zapre DB sejo.
    
    Zakaj uporabljamo yield namesto return? Ker tako FastAPI zagotovi,
    da se seja vedno zapre (tudi če pride do izjeme v handlerju).
    try/finally blok je ključen za preprečevanje puščanja povezav.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Ustvari vse tabele in izvede lahke idempotentne migracije.
    
    Zakaj ne uporabljamo Alembic? Ker je shema majhna in stabilna.
    Vsaka migracija je dodana kot 'ALTER TABLE ... ADD COLUMN IF NOT EXISTS'
    stavek, kar je varno za večkratni zagon (idempotentno).
    
    Trenutne migracije:
    - series_id v reservations: dodano za podporo serijskim rezervacijam
      (tedenske in celodnevne serije za admin/vodstvo).
    - name v reservations: ime serijske rezervacije (prikaz "Dogodek",
      če je prazno).
    """
    import app.models  # noqa: F401 – ensure models are registered

    Base.metadata.create_all(bind=engine)

    # ── Lahke idempotentne migracije ─────────────────────────────────────
    # Vsak stavek v LASTNI transakciji + IF NOT EXISTS. Zakaj?
    # PostgreSQL po napaki (npr. DuplicateColumn) označi celotno transakcijo
    # kot aborted — vsi nadaljnji ukazi v isti transakciji tiho padejo z
    # InFailedSqlTransaction. Stari pristop (vsi ALTER-ji v enem engine.begin()
    # + try/except pass) je zato na obstoječi bazi tiho preskočil vse
    # migracije za prvim že-obstoječim stolpcem.
    def _migrate(statement: str) -> None:
        try:
            with engine.begin() as conn:
                conn.execute(text(statement))
        except Exception:
            pass  # Že obstaja / že izvedeno — to je OK

    # Migracija: dodaj stolpec series_id v tabelo reservations
        _migrate("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS series_id VARCHAR")
        # Index za series_id
        _migrate("CREATE INDEX IF NOT EXISTS ix_reservations_series_id ON reservations (series_id)")
        # Migracija: dodaj stolpec name v tabelo reservations (ime serije)
        _migrate("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS name VARCHAR")

        # ── Nova tabela: activity_days (UI "Vnos dejavnosti") ─────────────
        # Idempotenten CREATE TABLE, da ne pade na obstoječi bazi. Base.metadata
        # create_all() zgoraj že ustvari tabelo, če model obstaja — ta blok je
        # zgolj varnostna mreža za čiste/obstoječe baze brez Alembic.
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
            "updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now()"
            ")"
        )
        _migrate("CREATE INDEX IF NOT EXISTS ix_activity_days_grade ON activity_days (grade)")
        _migrate("CREATE INDEX IF NOT EXISTS ix_activity_days_section ON activity_days (section)")


def log_audit(db: Session, user_id: int, user_name: str, action: str,
              entity_type: str, entity_id: int | None = None,
              details: str | None = None) -> None:
    """Zapiši dogodek v audit_log tabelo. Kličeš pred commitom.
    
    Zakaj se ta funkcija podvaja z app/audit.py?
    Zgodovinski razlog — ta verzija obstaja v database.py iz prejšnje
    arhitekture in se še vedno uporablja na nekaterih mestih. Novejša
    koda uporablja app.audit.log_audit, ki samostojno commit-a.
    """
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
