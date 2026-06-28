from datetime import datetime

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_audit(
    db: Session,
    user_id: int | None,
    username: str | None,
    action: str,
    details: str | None = None,
):
    """Zapiši dogodek v audit log."""
    entry = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        details=details,
        timestamp=datetime.utcnow(),
    )
    db.add(entry)
    db.flush()  # flush, ne commit — kličeš znotraj obstoječe transakcije
