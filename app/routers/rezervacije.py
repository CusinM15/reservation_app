from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from datetime import date as DateType

from app.database import get_db
from app.models import Reservation, User
from app.schemas import ReservationCreate, ReservationOut
from app.config import settings

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
    # Attach teacher_name
    for r in results:
        r.teacher_name = r.teacher.username if r.teacher else None
    return results

@router.post("", response_model=ReservationOut, status_code=201)
def create_rezervacija(data: ReservationCreate, db: Session = Depends(get_db)):
    _validate_prostor(data.prostor)
    _validate_razred(data.razred)
    _validate_hour(data.hour)
    
    if data.prostor == "tablice" and data.qty is None:
        raise HTTPException(status_code=400, detail="Za tablice morate navesti število (qty)")
    
    _check_tablice_capacity(db, data.prostor, data.date, data.hour, data.qty or 0)
    _check_unique_space(db, data.prostor, data.date, data.hour)
    
    reservation = Reservation(**data.model_dump())
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation

@router.delete("/{id}")
def delete_rezervacija(id: int, db: Session = Depends(get_db)):
    reservation = db.query(Reservation).filter(Reservation.id == id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Rezervacija ne obstaja")
    
    db.delete(reservation)
    db.commit()
    return {"message": "Rezervacija izbrisana"}
