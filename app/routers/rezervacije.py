from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from datetime import date as DateType, timedelta
import uuid
from collections import defaultdict

from app.database import get_db, log_audit
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
from app.routers.blocked_dates import _send_email
from app.audit import log_audit

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
        
        # Audit log — pred commitom, da je v isti transakciji
        log_audit(db, user_id=int(request.cookies.get("user_id") or 0), username=user_name,
                  action="create_rezervacija",
                  details=f"prostor={data.prostor}, date={data.date}, hour={data.hour}, razred={data.razred}, qty={data.qty}")

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
    
    user_name = f"{current_user.first_name} {current_user.last_name}".strip() or current_user.username

    # Audit log pred brisanjem (v isti transakciji)
    log_audit(db, user_id=current_user.id, username=user_name,
              action="delete_rezervacija",
              details=f"id={id}, prostor={reservation.prostor}, date={reservation.date}, hour={reservation.hour}, teacher_id={reservation.teacher_id}")

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


def _resolve_conflicts_and_notify(
    db: Session,
    planned: list[tuple[DateType, int]],
    *,
    prostor: str,
    creator_name: str,
    creator_id: int,
    qty: int | None,
) -> int:
    """Poišči konfliktne rezervacije, jih pobriši in pošlji email prvotnemu lastniku.
    Vrne število pobrisanih konfliktnih rezervacij."""
    removed = 0
    for d, h in planned:
        if prostor == "tablice":
            existing = db.query(Reservation).options(joinedload(Reservation.teacher)).filter(
                Reservation.prostor == "tablice",
                Reservation.date == d,
                Reservation.hour == h,
            ).all()
            need = qty or 0
            if existing:
                still_used = sum(r.qty or 0 for r in existing)
            else:
                still_used = 0
            while still_used + need > settings.TABLICE_MAX and existing:
                res = existing.pop(0)
                teacher = res.teacher
                date_str = d.strftime("%d.%m.%Y")
                hour_key = str(h)
                hour_label = settings.SCHEDULE.get(hour_key, f"ura {h}")
                db.delete(res)
                log_audit(
                    db, creator_id, creator_name, "delete", "reservation", res.id,
                    f"Avtomatsko izbrisana rezervacija (serija): tablice, {d}, {h}. ura"
                )
                removed += 1
                still_used = sum(r.qty or 0 for r in existing)
                if teacher and teacher.email:
                    _send_email(
                        to_email=teacher.email,
                        subject=f"Rezervacija za tablice preklicana — {date_str} {hour_label}",
                        body=f"Pozdravljeni,\n\n"
                             f"vaša rezervacija za **tablice** na dan {date_str} ob {hour_label} "
                             f"je bila preklicana, ker je {creator_name} ustvaril(a) serijsko "
                             f"rezervacijo, ki pokriva ta termin.\n\n"
                             f"Lep pozdrav,\nŠolski App"
                    )
        else:
            existing = db.query(Reservation).options(joinedload(Reservation.teacher)).filter(
                Reservation.prostor == prostor,
                Reservation.date == d,
                Reservation.hour == h,
            ).first()
            if existing:
                teacher = existing.teacher
                date_str = d.strftime("%d.%m.%Y")
                hour_key = str(h)
                hour_label = settings.SCHEDULE.get(hour_key, f"ura {h}")
                prostor_label = {"tablice": "tablice", "racunalnica": "računalnico", "ladja": "ladjo"}.get(prostor, prostor)
                db.delete(existing)
                log_audit(
                    db, creator_id, creator_name, "delete", "reservation", existing.id,
                    f"Avtomatsko izbrisana rezervacija (serija): {prostor_label}, {d}, {h}. ura"
                )
                removed += 1
                if teacher and teacher.email:
                    _send_email(
                        to_email=teacher.email,
                        subject=f"Rezervacija za {prostor} preklicana — {date_str} {hour_label}",
                        body=f"Pozdravljeni,\n\n"
                             f"vaša rezervacija za {prostor_label} na dan {date_str} ob {hour_label} "
                             f"je bila preklicana, ker je {creator_name} ustvaril(a) serijsko "
                             f"rezervacijo, ki pokriva ta termin.\n\n"
                             f"Lep pozdrav,\nŠolski App"
                    )
    return removed


def _commit_series(
    db: Session,
    planned: list[tuple[DateType, int]],
    *,
    prostor: str,
    teacher_id: int,
    creator_name: str,
    creator_id: int,
    qty: Optional[int],
) -> SeriesResult:
    """Ustvari serijske rezervacije. Obstoječe konfliktne rezervacije se avtomatsko
    pobrišejo, prvotni lastnik pa dobi email obvestilo."""
    _validate_prostor(prostor)
    for _, h in planned:
        _validate_hour(h)
    if prostor == "tablice" and qty is None:
        raise HTTPException(status_code=400, detail="Za tablice morate navesti število (qty)")

    # 1) Pobriši konfliktne rezervacije in pošlji obvestila
    removed = _resolve_conflicts_and_notify(db, planned, prostor=prostor, creator_name=creator_name, creator_id=creator_id, qty=qty)

    # 2) Ustvari nove zapise
    series_id = str(uuid.uuid4())
    for d, h in planned:
        db.add(Reservation(
            prostor=prostor,
            date=d,
            hour=h,
            teacher_id=teacher_id,
            qty=qty,
            series_id=series_id,
        ))

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Napaka pri shranjevanju serije: {e}")

    log_audit(db, user_id=teacher_id, username=creator_name,
              action="create_series",
              details=f"series_id={series_id}, prostor={prostor}, dates={len(planned)}x, removed={removed}")
    return SeriesResult(series_id=series_id, created=len(planned), skipped=[], removed=removed)


@router.post("/series/weekly", response_model=SeriesResult, status_code=201)
def create_weekly_series(
    data: WeeklySeriesCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Vsak teden isti dan, ista ura, med date_from in date_to. Samo admin/vodstvo."""
    user = _require_admin_or_vodstvo(request, db)
    creator_name = f"{user.first_name} {user.last_name}".strip() or user.username

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
        teacher_id=user.id,
        creator_name=creator_name,
        creator_id=user.id,
        qty=data.qty,
    )


@router.post("/series/full-day", response_model=SeriesResult, status_code=201)
def create_full_day_series(
    data: FullDaySeriesCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Vse ure (privzeto 0..7) za vsak dan v razponu. Samo admin/vodstvo."""
    user = _require_admin_or_vodstvo(request, db)
    creator_name = f"{user.first_name} {user.last_name}".strip() or user.username

    if data.date_to < data.date_from:
        raise HTTPException(status_code=400, detail="date_to mora biti >= date_from")

    hours = data.hours if data.hours else list(range(0, 8))
    for h in hours:
        if h < 0 or h > 7:
            raise HTTPException(status_code=400, detail=f"Neveljavna ura: {h}")

    planned: list[tuple[DateType, int]] = []
    d = data.date_from
    while d <= data.date_to:
        # Preskoči vikend (sobota=5, nedelja=6) — šola ne dela.
        if d.weekday() < 5:
            for h in hours:
                planned.append((d, h))
        d += timedelta(days=1)

    if not planned:
        raise HTTPException(status_code=400, detail="V podanem razponu ni delovnih dni.")

    return _commit_series(
        db, planned,
        prostor=data.prostor,
        teacher_id=user.id,
        creator_name=creator_name,
        creator_id=user.id,
        qty=data.qty,
    )


@router.get("/series", response_model=list[dict])
def list_all_series(
    request: Request,
    db: Session = Depends(get_db),
):
    """Vrne vse serije (bodoče) s povzetkom — prostor, termin, št. datumov, ustvarjalec."""
    from datetime import date
    today = date.today()
    rows = db.query(Reservation).options(joinedload(Reservation.teacher)).filter(
        Reservation.series_id.isnot(None),
        Reservation.date >= today,
    ).order_by(Reservation.date).all()

    # Group by series_id
    groups = defaultdict(list)
    for r in rows:
        groups[r.series_id].append(r)

    result = []
    for series_id, items in groups.items():
        items.sort(key=lambda x: x.date)
        first = items[0]
        last = items[-1]
        teacher_name = ""
        if first.teacher:
            teacher_name = f"{first.teacher.first_name} {first.teacher.last_name}".strip() or first.teacher.username
        # Build date list
        dates = sorted(set(r.date for r in items))
        result.append({
            "series_id": series_id,
            "prostor": first.prostor,
            "hour": first.hour,  # None for full-day series
            "date_from": dates[0].isoformat(),
            "date_to": dates[-1].isoformat(),
            "date_count": len(dates),
            "total_entries": len(items),
            "teacher_name": teacher_name,
            "teacher_id": first.teacher_id,
        })

    result.sort(key=lambda x: x["date_from"])
    return result


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
    user_name = f"{current.first_name} {current.last_name}".strip() or current.username
    log_audit(
        db, current.id, user_name, "delete", "series", None,
        f"Izbrisana serija ({n} terminov): {rows[0].prostor}, od {min(r.date for r in rows)} do {max(r.date for r in rows)}"
    )
    for r in rows:
        db.delete(r)
    db.commit()
    log_audit(db, user_id=current.id, username=f"{current.first_name} {current.last_name}".strip() or current.username,
              action="delete_series",
              details=f"series_id={series_id}, deleted={n}")
    return {"message": f"Serija izbrisana ({n} terminov)", "deleted": n}
