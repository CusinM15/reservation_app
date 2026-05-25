from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from datetime import date, datetime, timedelta
from typing import Optional, List
from calendar import monthrange

from app.database import get_db
from app.models import Assessment, User, RoleEnum, BlockedDate
from app.schemas import AssessmentCreate, AssessmentOut
from app.config import settings
from app.race import register_intent, check_and_raise, cleanup, get_lock
import smtplib, ssl
from email.mime.text import MIMEText

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
    
    # Normal assessment: max 2 normal assessments per week
    # Ponavljanje: max 3 total assessments per week
    if je_ponavljanje:
        max_allowed = 3
        if len(assessments) >= max_allowed:
            detail = f"V tem tednu ({week_start.strftime('%d.%m.%Y')}-{week_end.strftime('%d.%m.%Y')}) so že 3 ocenjevanja. Za ponavljanje je dovoljeno maksimalno 3."
            raise HTTPException(status_code=400, detail=detail)
    else:
        # Only count existing normal assessments for the normal limit
        normal_count = sum(1 for a in assessments if not a.ponavljanje)
        if normal_count >= 2:
            detail = f"V tem tednu ({week_start.strftime('%d.%m.%Y')}-{week_end.strftime('%d.%m.%Y')}) so že 2 običajni ocenjevanji."
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
        teacher = a.teacher
        if teacher:
            full = f"{teacher.first_name} {teacher.last_name}".strip()
            a.teacher_name = full if full else teacher.username
        else:
            a.teacher_name = None
    return results

@router.post("", response_model=AssessmentOut, status_code=201)
def create_ocenjevanje(data: AssessmentCreate, request: Request, db: Session = Depends(get_db)):
    _validate_razred(data.razred)
    
    # Get current user name
    user_id = request.cookies.get("user_id")
    current_user = db.query(User).filter(User.id == int(user_id)).first() if user_id else None
    user_name = f"{current_user.first_name} {current_user.last_name}".strip() if current_user else "?"
    
    # Resource key for race detection
    resource_key = f"ocenjevanje:{data.razred}:{data.date}"
    
    lock = get_lock(resource_key)
    register_intent(resource_key, user_id, user_name)
    
    with lock:
        # Check for race condition
        other = check_and_raise(resource_key, user_id)
        if other:
            raise HTTPException(
                status_code=409,
                detail=f"Termin ocenjevanja je v istem trenutku napovedal tudi {other}. Oba sta bila zavrnjena."
            )
        
        # Preveri tedenske omejitve
        _check_weekly_limit(db, data.razred, data.date, data.ponavljanje)
        
        assessment = Assessment(**data.model_dump())
        db.add(assessment)
        try:
            db.commit()
            db.refresh(assessment)
        except Exception:
            db.rollback()
            raise HTTPException(status_code=500, detail="Napaka pri shranjevanju ocenjevanja")
        
        # Check if this date is blocked for this class → send email to blocker
        try:
            blocked = db.query(BlockedDate).filter(
                BlockedDate.razred == data.razred,
                BlockedDate.date == data.date
            ).first()
            if blocked:
                creator = db.query(User).filter(User.id == blocked.created_by_id).first()
                assessor = current_user
                if creator and creator.email and settings.MAIL_PASSWORD:
                    msg = MIMEText(
                        f"Pozdravljeni,\n\n"
                        f"{assessor.first_name} {assessor.last_name} je napovedal(a) ocenjevanje za "
                        f"{data.razred} na dan {data.date}, "
                        f"čeprav ste ta dan označili kot zasedenega.\n\n"
                        f"Lep pozdrav,\nŠolski App"
                    )
                    msg["Subject"] = f"Ocenjevanje za {data.razred} na zaseden datum {data.date}"
                    msg["From"] = settings.MAIL_FROM
                    msg["To"] = creator.email
                    context = ssl.create_default_context()
                    with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as s:
                        s.starttls(context=context)
                        s.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
                        s.send_message(msg)
        except Exception:
            pass  # email is best-effort
        
        cleanup(resource_key)
        return assessment

@router.delete("/{id}")
def delete_ocenjevanje(id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    
    current_user = db.query(User).filter(User.id == int(user_id)).first()
    if not current_user:
        raise HTTPException(status_code=401, detail="Uporabnik ne obstaja")
    
    assessment = db.query(Assessment).filter(Assessment.id == id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Ocenjevanje ne obstaja")
    
    # Only the creator or admin can delete
    if assessment.teacher_id != current_user.id and current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Samo avtor ali admin lahko briše ocenjevanje")
    
    db.delete(assessment)
    db.commit()
    return {"message": "Ocenjevanje izbrisano"}
