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
from app.models import AuditLog, School, User, RoleEnum
from app.config import settings
from app.security import get_current_user_id
from app.tenancy import (
    MAIN_ADMIN_ROLE,
    data_school_id,
    get_request_user,
    is_main_admin,
    role_value,
    scope,
)

router = APIRouter(prefix="/api/audit-log", tags=["audit-log"])
templates = Jinja2Templates(directory="app/templates")


def _require_admin(request: Request, db: Session):
    """Preveri, da je uporabnik admin (šolski) ali glavni admin. Vrne uporabnika.
    
    Zakaj tudi glavni admin? Ker ta vidi podatke vseh šol — audit log je
    del teh podatkov. Šolski admin vidi samo dogodke svoje šole
    (filtriranje po school_id v list_audit_log).
    """
    user = get_request_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    if role_value(user) not in (RoleEnum.admin.value, MAIN_ADMIN_ROLE):
        raise HTTPException(status_code=403, detail="Samo admin lahko vidi audit log")
    return user


@router.get("")
def list_audit_log(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    school_id: int | None = Query(None, description="Filter po šoli (samo glavni admin)"),
    db: Session = Depends(get_db),
):
    """JSON endpoint — vrni zadnje vnose v audit logu.

    Podpira paginacijo (offset/limit), filtriranje po vrsti akcije in — za
    GLAVNEGA admina — filtriranje po šoli (``school_id``; brez njega vse šole).
    Vsaka vrstica nosi tudi ime šole (stolpec »Šola« v UI).
    Šolski admin vidi izključno dogodke svoje šole (parameter school_id se
    ignorira — to je varnostna meja, ne preference).

    Rezultati so urejeni po ID-ju descending (najnovejši prvi).
    """
    user = _require_admin(request, db)

    # Obseg podatkov: šolski admin vedno samo svoja šola; glavni admin vse
    # (ali izbrana šola iz parametra oz. konteksta).
    if is_main_admin(user):
        chosen = school_id if school_id is not None else data_school_id(request, db)
    else:
        chosen = data_school_id(request, db)

    query = scope(db.query(AuditLog).options(joinedload(AuditLog.user)), AuditLog, chosen)
    if action:
        query = query.filter(AuditLog.action == action)
    total = query.count()
    rows = query.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()

    # Imena šol za stolpec »Šola« (in za spustni seznam pri glavnem adminu).
    schools = [
        {"id": s.id, "name": s.name}
        for s in db.query(School).order_by(School.name).all()
    ]
    names = {s["id"]: s["name"] for s in schools}

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
            "school_id": r.school_id,
            "school": names.get(r.school_id) if r.school_id else None,
        })
    return {
        "total": total,
        "rows": result,
        "schools": schools if is_main_admin(user) else [],
        "is_main_admin": is_main_admin(user),
        "filter_school_id": chosen,
    }


@router.get("/page", response_class=HTMLResponse)
def audit_log_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """HTML stran za ogled audit loga (samo admin)."""
    user = _require_admin(request, db)
    schools = []
    if is_main_admin(user):
        schools = [
            {"id": s.id, "name": s.name}
            for s in db.query(School).order_by(School.name).all()
        ]
    return templates.TemplateResponse("audit_log.html", {
        "request": request,
        "is_main_admin": is_main_admin(user),
        "schools": schools,
    })
