# ─────────────────────────────────────────────────────────────────────────
# app/routers/audit_log.py — Ogled audit loga (samo admin)
#
# Namen: JSON in HTML endpointa za pregledovanje audit log zapisov.
# Dostopno samo uporabnikom z vlogo 'admin'.
#
# Zakaj JSON in HTML?
# JSON endpoint (/api/audit-log) uporablja JavaScript v UI za dinamično
# nalaganje. HTML endpoint (/api/audit-log/page) je za neposreden ogled.
# ─────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import AuditLog, User, RoleEnum
from app.config import settings

router = APIRouter(prefix="/api/audit-log", tags=["audit-log"])
templates = Jinja2Templates(directory="app/templates")


def _require_admin(request: Request, db: Session):
    """Preveri, da je uporabnik admin. Vrne uporabnika.
    
    Samo admin lahko vidi audit log — tudi vodstvo nima te pravice,
    ker audit log vsebuje občutljive podatke o brisanju uporabnikov
    in spremembah vlog.
    """
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Uporabnik ne obstaja")
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Samo admin lahko vidi audit log")
    return user


@router.get("")
def list_audit_log(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """JSON endpoint — vrni zadnje vnose v audit logu.
    
    Podpira paginacijo (offset/limit) in filtriranje po vrsti akcije.
    Vrne tudi skupno število zadetkov (total) za potrebe UI.
    
    Rezultati so urejeni po ID-ju descending (najnovejši prvi).
    """
    _require_admin(request, db)

    query = db.query(AuditLog).options(joinedload(AuditLog.user))
    if action:
        query = query.filter(AuditLog.action == action)
    total = query.count()
    rows = query.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()

    result = []
    for r in rows:
        u = r.user
        result.append({
            "id": r.id,
            "user_id": r.user_id,
            "username": r.username or (u.username if u else None),
            "action": r.action,
            "details": r.details,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        })
    return {"total": total, "rows": result}


@router.get("/page", response_class=HTMLResponse)
def audit_log_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """HTML stran za ogled audit loga (samo admin)."""
    _require_admin(request, db)
    return templates.TemplateResponse("audit_log.html", {"request": request})
