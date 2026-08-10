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
    """
    import app.models  # noqa: F401 – ensure models are registered

    Base.metadata.create_all(bind=engine)

    # ── Lahka migracija: dodaj series_id v reservations, če manjka ──
    # try/except namesto IF NOT EXISTS zaradi idempotentnosti —
    # stavek se izvede ob vsakem zagonu, kolona/index pa obstajata
    # samo enkrat.
    with engine.begin() as conn:
        # Migracija: dodaj stolpec series_id v tabelo reservations
        try:
            conn.execute(text(
                "ALTER TABLE reservations ADD COLUMN series_id VARCHAR"
            ))
        except Exception:
            pass  # Kolona že obstaja — to je OK

        # Index za series_id (prav tako s try/except)
        try:
            conn.execute(text(
                "CREATE INDEX ix_reservations_series_id "
                "ON reservations (series_id)"
            ))
        except Exception:
            pass  # Index že obstaja


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
