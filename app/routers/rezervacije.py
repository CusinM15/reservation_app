from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from datetime import date as DateType, timedelta
import uuid

from app.database import get_db
from app.models import Reservation, User, RoleEnum
from app.schemas import (
    ReservationCreate,
    ReservationOut,
    WeeklySeriesCreate,
    FullDaySeriesCreate,
    SeriesResult,
)
from app.config import settings
from app.race import register_intent, check_and_raise, cleanup, get_lock

router = APIRouter(prefix="/api/rezervacije", tags=["rezervacije"])

def _validate_prostor(prostor: str):
    if prostor not in settings.PROSTORI:
        raise HTTPException(status_code=400, detail=f"Neveljaven prostor: {prostor}")

def _validate_razred(razred: str):
    if razred not in settings.RAZREDI:
        raise HTTPException(status_code=400, detail=f"Neveljaven razred: {razred}")

def _validate_hour(hour: int):
    if hour < 0 or hour > 7:
        raise HTTPException(status_code=400, detail="Ura mora biti med 0 in 7")

def _check_tablice_capacity(db: Session, prostor: str, date: DateType, hour: int, qty: int):
    if prostor != "tablice":
        return
    
    existing = db.query(Reservation).filter(
        Reservation.prostor == "tablice",
        Reservation.date == date,
        Reservation.hour == hour
    ).all()
    
    total_used = sum(r.qty or 0 for r in existing)
    if total_used + qty > settings.TABLICE_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Skupno število tablet ({total_used + qty}) presega kapaciteto ({settings.TABLICE_MAX})"
        )

def _check_unique_space(db: Session, prostor: str, date: DateType, hour: int):
    if prostor == "tablice":
        return
    
    existing = db.query(Reservation).filter(
        Reservation.prostor == prostor,
        Reservation.date == date,
        Reservation.hour == hour
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Ta termin je že zaseden.")

@router.get("", response_model=list[ReservationOut])
def list_rezervacije(
    date: Optional[DateType] = Query(None),
    date_from: Optional[DateType] = Query(None),
    date_to: Optional[DateType] = Query(None),
    prostor: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Reservation).options(joinedload(Reservation.teacher))
    if date:
        query = query.filter(Reservation.date == date)
    if date_from:
        query = query.filter(Reservation.date >= date_from)
    if date_to:
        query = query.filter(Reservation.date <= date_to)
    if prostor:
        query = query.filter(Reservation.prostor == prostor)
    results = query.order_by(Reservation.date, Reservation.hour).all()
    # Attach teacher_name (full name)
    for r in results:
        teacher = r.teacher
        if teacher:
            full = f"{teacher.first_name} {teacher.last_name}".strip()
            r.teacher_name = full if full else teacher.username
        else:
            r.teacher_name = None
    return results

@router.post("", response_model=ReservationOut, status_code=201)
def create_rezervacija(data: ReservationCreate, request: Request, db: Session = Depends(get_db)):
    _validate_prostor(data.prostor)
    if data.razred:
        _validate_razred(data.razred)
    _validate_hour(data.hour)
    
    if data.prostor == "tablice" and data.qty is None:
        raise HTTPException(status_code=400, detail="Za tablice morate navesti število (qty)")
    
    # Get current user name
    user_id = request.cookies.get("user_id")
    current_user = db.query(User).filter(User.id == int(user_id)).first() if user_id else None
    user_name = f"{current_user.first_name} {current_user.last_name}".strip() if current_user else "?"
    
    # Build a resource key for race detection
    resource_key = f"rezervacija:{data.prostor}:{data.date}:{data.hour}"
    if data.prostor == "tablice":
        resource_key = f"tablice:{data.date}:{data.hour}"
    
    lock = get_lock(resource_key)
    register_intent(resource_key, user_id, user_name)
    
    with lock:
        # Check for race condition
        other = check_and_raise(resource_key, user_id)
        if other:
            raise HTTPException(
                status_code=409,
                detail=f"Termin je v istem trenutku rezerviral tudi {other}. Oba sta bila zavrnjena."
            )
        
        # Now do the actual checks
        _check_tablice_capacity(db, data.prostor, data.date, data.hour, data.qty or 0)
        _check_unique_space(db, data.prostor, data.date, data.hour)
        
        reservation = Reservation(**data.model_dump())
        db.add(reservation)
        try:
            db.commit()
            db.refresh(reservation)
        except Exception:
            db.rollback()
            raise HTTPException(status_code=500, detail="Napaka pri shranjevanju rezervacije")
        
        cleanup(resource_key)
        return reservation

@router.delete("/{id}")
def delete_rezervacija(id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    
    current_user = db.query(User).filter(User.id == int(user_id)).first()
    if not current_user:
        raise HTTPException(status_code=401, detail="Uporabnik ne obstaja")
    
    reservation = db.query(Reservation).filter(Reservation.id == id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Rezervacija ne obstaja")
    
    # Only the creator, admin or vodstvo can delete
    if reservation.teacher_id != current_user.id and current_user.role not in (RoleEnum.admin, RoleEnum.vodstvo):
        raise HTTPException(status_code=403, detail="Samo avtor, admin ali vodstvo lahko briše rezervacijo")
    
    db.delete(reservation)
    db.commit()
    return {"message": "Rezervacija izbrisana"}


# ── Serijske rezervacije ────────────────────────────────────────────
#
# Samo admin in vodstvo lahko ustvarijo (ali zbrišejo) serijo. Učitelji
# delajo enkratne rezervacije preko standardnega POST /api/rezervacije.

def _require_admin_or_vodstvo(request: Request, db: Session) -> User:
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Uporabnik ne obstaja")
    if user.role not in (RoleEnum.admin, RoleEnum.vodstvo):
        raise HTTPException(
            status_code=403,
            detail="Serijske rezervacije lahko ustvarja samo admin ali vodstvo.",
        )
    return user


def _conflict_reason(db: Session, prostor: str, d: DateType, hour: int, qty: int | None) -> str | None:
    """Vrne razlog konflikta ali None, če je termin prost. Brez vrženja izjeme."""
    if prostor == "tablice":
        existing = db.query(Reservation).filter(
            Reservation.prostor == "tablice",
            Reservation.date == d,
            Reservation.hour == hour,
        ).all()
        used = sum(r.qty or 0 for r in existing)
        need = qty or 0
        if used + need > settings.TABLICE_MAX:
            return f"tablice presežene ({used}+{need} > {settings.TABLICE_MAX})"
        return None
    existing = db.query(Reservation).filter(
        Reservation.prostor == prostor,
        Reservation.date == d,
        Reservation.hour == hour,
    ).first()
    if existing:
        return "termin že zaseden"
    return None


def _commit_series(
    db: Session,
    planned: list[tuple[DateType, int]],
    *,
    prostor: str,
    razred: Optional[str],
    teacher_id: int,
    qty: Optional[int],
    skip_conflicts: bool,
) -> SeriesResult:
    """Skupna logika: planned = seznam (date, hour). Vse ali nič, razen če skip_conflicts."""
    _validate_prostor(prostor)
    if razred:
        _validate_razred(razred)
    for _, h in planned:
        _validate_hour(h)
    if prostor == "tablice" and qty is None:
        raise HTTPException(status_code=400, detail="Za tablice morate navesti število (qty)")

    # 1) prečekiraj vse konflikte vnaprej
    conflicts: list[dict] = []
    for d, h in planned:
        reason = _conflict_reason(db, prostor, d, h, qty)
        if reason:
            conflicts.append({"date": d.isoformat(), "hour": h, "reason": reason})

    if conflicts and not skip_conflicts:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Serija ima konflikte. Pošlji skip_conflicts=true za delno rezervacijo.",
                "conflicts": conflicts,
            },
        )

    # 2) ustvari zapise (preskoči konfliktne, če skip_conflicts)
    series_id = str(uuid.uuid4())
    conflict_keys = {(c["date"], c["hour"]) for c in conflicts}
    created = 0
    for d, h in planned:
        if (d.isoformat(), h) in conflict_keys:
            continue
        db.add(Reservation(
            prostor=prostor,
            date=d,
            hour=h,
            razred=razred or "",
            teacher_id=teacher_id,
            qty=qty,
            series_id=series_id,
        ))
        created += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Napaka pri shranjevanju serije: {e}")

    return SeriesResult(series_id=series_id, created=created, skipped=conflicts)


@router.post("/series/weekly", response_model=SeriesResult, status_code=201)
def create_weekly_series(
    data: WeeklySeriesCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Vsak teden isti dan, ista ura, med date_from in date_to. Samo admin/vodstvo."""
    _require_admin_or_vodstvo(request, db)

    if data.date_to < data.date_from:
        raise HTTPException(status_code=400, detail="date_to mora biti >= date_from")

    # Najdi prvi datum >= date_from, ki ustreza weekday
    first = data.date_from
    delta = (data.weekday - first.weekday()) % 7
    first = first + timedelta(days=delta)

    planned: list[tuple[DateType, int]] = []
    d = first
    while d <= data.date_to:
        planned.append((d, data.hour))
        d += timedelta(days=7)

    if not planned:
        raise HTTPException(status_code=400, detail="V podanem razponu ni nobenega ustreznega dne.")

    return _commit_series(
        db, planned,
        prostor=data.prostor,
        razred=data.razred,
        teacher_id=data.teacher_id,
        qty=data.qty,
        skip_conflicts=data.skip_conflicts,
    )


@router.post("/series/full-day", response_model=SeriesResult, status_code=201)
def create_full_day_series(
    data: FullDaySeriesCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Vse ure (privzeto 0..7) za vsak dan v razponu. Samo admin/vodstvo."""
    _require_admin_or_vodstvo(request, db)

    if data.date_to < data.date_from:
        raise HTTPException(status_code=400, detail="date_to mora biti >= date_from")

    hours = data.hours if data.hours else list(range(0, 8))
    for h in hours:
        if h < 0 or h > 7:
            raise HTTPException(status_code=400, detail=f"Neveljavna ura: {h}")

    planned: list[tuple[DateType, int]] = []
    d = data.date_from
    while d <= data.date_to:
        # Preskoči vikend (sobota=5, nedelja=6) — šola ne dela. Če bi želel
        # rezervirati tudi vikend, lahko to spremeniš ali doda flag.
        if d.weekday() < 5:
            for h in hours:
                planned.append((d, h))
        d += timedelta(days=1)

    if not planned:
        raise HTTPException(status_code=400, detail="V podanem razponu ni delovnih dni.")

    return _commit_series(
        db, planned,
        prostor=data.prostor,
        razred=data.razred,
        teacher_id=data.teacher_id,
        qty=data.qty,
        skip_conflicts=data.skip_conflicts,
    )


@router.get("/series/{series_id}", response_model=list[ReservationOut])
def list_series(series_id: str, db: Session = Depends(get_db)):
    """Vrni vse rezervacije, ki pripadajo dani seriji."""
    rows = db.query(Reservation).options(joinedload(Reservation.teacher)).filter(
        Reservation.series_id == series_id
    ).order_by(Reservation.date, Reservation.hour).all()
    for r in rows:
        t = r.teacher
        if t:
            full = f"{t.first_name} {t.last_name}".strip()
            r.teacher_name = full if full else t.username
    return rows


@router.delete("/series/{series_id}")
def delete_series(series_id: str, request: Request, db: Session = Depends(get_db)):
    """Pobriši celotno serijo. Samo admin/vodstvo ali avtor cele serije."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    current = db.query(User).filter(User.id == int(user_id)).first()
    if not current:
        raise HTTPException(status_code=401, detail="Uporabnik ne obstaja")

    rows = db.query(Reservation).filter(Reservation.series_id == series_id).all()
    if not rows:
        raise HTTPException(status_code=404, detail="Serija ne obstaja")

    is_priv = current.role in (RoleEnum.admin, RoleEnum.vodstvo)
    is_owner = all(r.teacher_id == current.id for r in rows)
    if not (is_priv or is_owner):
        raise HTTPException(status_code=403, detail="Samo admin/vodstvo ali avtor serije lahko briše.")

    n = len(rows)
    for r in rows:
        db.delete(r)
    db.commit()
    return {"message": f"Serija izbrisana ({n} terminov)", "deleted": n}
