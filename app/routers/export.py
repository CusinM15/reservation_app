# ─────────────────────────────────────────────────────────────────────────
# app/routers/export.py — CSV izvoz rezervacij in ocenjevanj
#
# Namen: Nudi bogatejše možnosti izvoza v CSV kot tisti v rezervacije.py.
# Samo admin in vodstvo lahko izvažata.
#
# Zakaj ločen modul od inline CSV izvoza v rezervacijah?
# Ta modul je novejši in omogoča boljše filtriranje (obvezno datumsko
# obdobje, prostor/razred opcijsko). Starejši CSV izvoz v rezervacije.py
# ostaja zaradi združljivosti nazaj.
# ─────────────────────────────────────────────────────────────────────────

import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Reservation, Assessment, User, RoleEnum
from app.security import get_current_user_id
from app.tenancy import data_school_id, get_request_user, role_value, scope

router = APIRouter(prefix="/api/export", tags=["export"])


def _require_admin_or_vodstvo(request: Request, db: Session) -> User:
    """Preveri, da je uporabnik admin ali vodstvo. Vrne uporabnika."""
    user = get_request_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    if role_value(user) not in (RoleEnum.admin.value, RoleEnum.vodstvo.value):
        raise HTTPException(status_code=403, detail="Samo admin in vodstvo lahko izvažata podatke")
    return user


@router.get("/rezervacije")
def export_rezervacije(
    request: Request,
    date_from: str = Query(..., description="Začetni datum (YYYY-MM-DD)"),
    date_to: str = Query(..., description="Končni datum (YYYY-MM-DD)"),
    prostor: str | None = Query(None, description="Filter po prostoru (prazen = vsi)"),
    db: Session = Depends(get_db),
):
    """Izvozi rezervacije v CSV za izbrano obdobje in prostor.
    
    CSV vsebuje: Datum, Ura, Prostor, Razred, Učitelj, Število tablic, Serija ID.
    Uporablja UTF-8 BOM (charset=utf-8-sig) za pravilen prikaz šumnikov v Excelu.
    """
    _require_admin_or_vodstvo(request, db)
    school_id = data_school_id(request, db)

    try:
        dt_from = date.fromisoformat(date_from)
        dt_to = date.fromisoformat(date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="Neveljaven format datuma. Uporabite YYYY-MM-DD")

    if dt_from > dt_to:
        raise HTTPException(status_code=400, detail="Začetni datum ne sme biti po končnem")

    query = scope(
        db.query(Reservation)
        .options(joinedload(Reservation.teacher))
        .filter(Reservation.date >= dt_from, Reservation.date <= dt_to),
        Reservation, school_id,
    ).order_by(Reservation.date, Reservation.hour, Reservation.prostor)

    if prostor:
        query = query.filter(Reservation.prostor == prostor)

    rezervacije = query.all()

    # CSV generation
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Datum", "Ura", "Prostor", "Razred", "Učitelj", "Število tablic", "Serija ID"])

    for r in rezervacije:
        teacher_name = ""
        if r.teacher:
            teacher_name = f"{r.teacher.first_name} {r.teacher.last_name}".strip() or r.teacher.username
        writer.writerow([
            r.date.isoformat(),
            r.hour,
            r.prostor,
            r.razred or "",
            teacher_name,
            r.qty or "",
            r.series_id or "",
        ])

    output.seek(0)

    filename = f"rezervacije_{date_from}_{date_to}"
    if prostor:
        filename += f"_{prostor}"
    filename += ".csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/ocenjevanja")
def export_ocenjevanja(
    request: Request,
    razred: str | None = Query(None, description="Filter po razredu (prazen = vsi)"),
    date_from: str = Query(..., description="Začetni datum (YYYY-MM-DD)"),
    date_to: str = Query(..., description="Končni datum (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """Izvozi ocenjevanja v CSV za izbrani razred in obdobje.
    
    CSV vsebuje: Datum, Razred, Tip (Ponavljanje/Običajno), Učitelj.
    """
    _require_admin_or_vodstvo(request, db)
    school_id = data_school_id(request, db)

    try:
        dt_from = date.fromisoformat(date_from)
        dt_to = date.fromisoformat(date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="Neveljaven format datuma. Uporabite YYYY-MM-DD")

    if dt_from > dt_to:
        raise HTTPException(status_code=400, detail="Začetni datum ne sme biti po končnem")

    query = scope(
        db.query(Assessment)
        .options(joinedload(Assessment.teacher))
        .filter(Assessment.date >= dt_from, Assessment.date <= dt_to),
        Assessment, school_id,
    ).order_by(Assessment.date, Assessment.razred)

    if razred:
        query = query.filter(Assessment.razred == razred)

    ocenjevanja = query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Datum", "Razred", "Tip", "Učitelj"])

    for o in ocenjevanja:
        teacher_name = ""
        if o.teacher:
            teacher_name = f"{o.teacher.first_name} {o.teacher.last_name}".strip() or o.teacher.username
        tip = "Ponavljanje" if o.ponavljanje else "Običajno"
        writer.writerow([
            o.date.isoformat(),
            o.razred,
            tip,
            teacher_name,
        ])

    output.seek(0)

    filename = f"ocenjevanja_{date_from}_{date_to}"
    if razred:
        filename += f"_{razred}"
    filename += ".csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
