from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={} if "postgresql" in settings.DATABASE_URL else {"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables and apply small idempotent migrations."""
    import app.models  # noqa: F401 – ensure models are registered
    Base.metadata.create_all(bind=engine)

    # ── Lahka migracija: dodaj series_id v reservations, če manjka ──
    # ADD COLUMN IF NOT EXISTS deluje na PostgreSQL >= 9.6 in na SQLite >= 3.35.
    # Brez Alembica, ker je sprememba trivialna (nullable kolona, brez FK).
    from sqlalchemy import text
    with engine.begin() as conn:
        try:
            conn.execute(text(
                "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS series_id VARCHAR"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_reservations_series_id "
                "ON reservations (series_id)"
            ))
        except Exception as e:
            # Če baza tega ne podpira (npr. zelo star SQLite), to ni fatalno —
            # nova kolona bo manjkala, ampak app še vedno teče za enkratne rez.
            print(f"[init_db] migracija series_id preskočena: {e}")


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
