from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from datetime import date, datetime, timedelta
from typing import Optional, List
from calendar import monthrange

from app.database import get_db
from app.models import Assessment, User
from app.schemas import AssessmentCreate, AssessmentOut
from app.config import settings

router = APIRouter(prefix="/api/ocenjevanja", tags=["ocenjevanja"])

def _validate_razred(razred: str):
    if razred not in settings.RAZREDI:
        raise HTTPException(status_code=400, detail="Neveljaven razred.")

def _get_week_start(d: date) -> date:
    """Vrne ponedeljek tedna za dan d"""
    return d - timedelta(days=d.weekday())

def _get_week_end(week_start: date) -> date:
    """Vrne nedeljo tedna"""
    return week_start + timedelta(days=6)

def _get_assessments_in_week(db: Session, razred: str, week_start: date) -> List[Assessment]:
    """Vrne vsa ocenjevanja za razred v danem tednu"""
    week_end = _get_week_end(week_start)
    return db.query(Assessment).filter(
        and_(
            Assessment.razred == razred,
            Assessment.date >= week_start,
            Assessment.date <= week_end
        )
    ).all()

def _check_consecutive_days(dates: List[date]) -> bool:
    """Preveri ali so 3 datumi zaporedni dnevi"""
    if len(dates) < 3:
        return False
    sorted_dates = sorted(dates)
    for i in range(len(sorted_dates) - 2):
        if (sorted_dates[i+1] - sorted_dates[i]).days == 1 and \
           (sorted_dates[i+2] - sorted_dates[i+1]).days == 1:
            return True
    return False

def _check_weekly_limit(db: Session, razred: str, nova_date: date, je_ponavljanje: bool):
    """Preveri tedenske omejitve za ocenjevanja"""
    week_start = _get_week_start(nova_date)
    week_end = _get_week_end(week_start)
    
    assessments = _get_assessments_in_week(db, razred, week_start)
    
    # Preveri ce ze obstaja na isti dan
    for a in assessments:
        if a.date == nova_date:
            raise HTTPException(
                status_code=400, 
                detail="V istem tednu ne morete imeti dveh ocenjevanj na isti dan."
            )
    
    max_allowed = 3 if je_ponavljanje else 2
    
    if len(assessments) >= max_allowed:
        if je_ponavljanje:
            detail = f"V tem tednu ({week_start.strftime('%d.%m.%Y')}-{week_end.strftime('%d.%m.%Y')}) so že 3 ocenjevanja. Za ponavljanje je dovoljeno maksimalno 3."
        else:
            detail = f"V tem tednu ({week_start.strftime('%d.%m.%Y')}-{week_end.strftime('%d.%m.%Y')}) so že 2 ocenjevanja."
        raise HTTPException(status_code=400, detail=detail)
    
    # Za ponavljanje preveri se 3 zaporedne dni
    if je_ponavljanje:
        vse_dates = [a.date for a in assessments] + [nova_date]
        if _check_consecutive_days(vse_dates):
            raise HTTPException(
                status_code=400,
                detail="Pri ponavljanju ocenjevanja ne smejo biti na 3 zaporedne dni (npr. pon, tor, sre)."
            )

@router.get("", response_model=List[AssessmentOut])
def list_ocenjevanja(
    razred: Optional[str] = Query(None),
    month: Optional[str] = Query(None, description="Format: YYYY-MM"),
    db: Session = Depends(get_db)
):
    query = db.query(Assessment).options(joinedload(Assessment.teacher))
    
    if razred:
        _validate_razred(razred)
        query = query.filter(Assessment.razred == razred)
    
    if month:
        try:
            year, month_num = map(int, month.split('-'))
            start_date = date(year, month_num, 1)
            last_day = monthrange(year, month_num)[1]
            end_date = date(year, month_num, last_day)
            query = query.filter(
                and_(
                    Assessment.date >= start_date,
                    Assessment.date <= end_date
                )
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Neveljaven format meseca. Uporabite YYYY-MM")
    
    results = query.order_by(Assessment.date).all()
    for a in results:
        a.teacher_name = a.teacher.username if a.teacher else None
    return results

@router.post("", response_model=AssessmentOut, status_code=201)
def create_ocenjevanje(data: AssessmentCreate, db: Session = Depends(get_db)):
    _validate_razred(data.razred)
    
    # Preveri tedenske omejitve
    _check_weekly_limit(db, data.razred, data.date, data.ponavljanje)
    
    assessment = Assessment(**data.model_dump())
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment

@router.delete("/{id}")
def delete_ocenjevanje(id: int, db: Session = Depends(get_db)):
    assessment = db.query(Assessment).filter(Assessment.id == id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Ocenjevanje ne obstaja")
    
    db.delete(assessment)
    db.commit()
    return {"message": "Ocenjevanje izbrisano"}
