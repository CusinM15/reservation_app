# ─────────────────────────────────────────────────────────────────────────
# app/routers/ocenjevanja.py — Endpointi za napovedovanje ocenjevanj
#
# Namen: CRUD za ocenjevanja s strogimi tedenskimi omejitvami.
#
# Pravila za ocenjevanja (določila šole):
# - Max 3 ocenjevanja na teden na razred (katerakoli vrsta)
# - Max 2 običajni (non-ponavljanje) na teden
# - Največ 1 ocenjevanje na dan na razred
# - Prepoved ocenjevanj na 3 zaporedne dni (npr. pon, tor, sre)
# - Če je datum za ta razred dan dejavnosti (BlockedDate), se ocenjevanje
#   zavrne s 400 — na dan dejavnosti ni možno napovedati ocenjevanja
#
# Zakaj so omejitve implementirane na nivoju API-ja in ne baze?
# Ker pravila vključujejo tedenske izračune (3 zaporedni dnevi, max 3/teden),
# kar je težko implementirati s SQL CHECK constraints. Poleg tega se
# pravila lahko spremenijo (npr. šola lahko dovoli 4 ocenjevanja na teden).
#
# Race condition zaščita: enaka kot pri rezervacijah — uporablja app.race.
# ─────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from datetime import date, datetime, timedelta
from typing import Optional, List
from calendar import monthrange

from app.database import get_db, log_audit
from app.models import Assessment, User, RoleEnum, BlockedDate
from app.schemas import AssessmentCreate, AssessmentOut
from app.config import settings
from app.race import register_intent, check_and_raise, cleanup, get_lock
from app.audit import log_audit
from app.security import get_current_user_id
from app.tenancy import (
    SchoolConfig,
    config_for_request,
    data_school_id,
    get_request_user,
    role_value,
    scope,
    write_school_id,
)

router = APIRouter(prefix="/api/ocenjevanja", tags=["ocenjevanja"])


# ── Pomožne validacijske funkcije ────────────────────────────────────
#
# Pravila ocenjevanja so NASTAVLJIVA PO ŠOLI (school_settings):
#   ASSESSMENT_MAX_PER_WEEK             — največ »običajnih« ocenjevanj na teden
#   ASSESSMENT_MAX_PER_DAY              — največ ocenjevanj na dan
#   ASSESSMENT_MAX_PER_WEEK_WITH_RETAKE — zgornja meja tedna, ko je vmes ponavljanje
#   ASSESSMENT_MAX_CONSECUTIVE_DAYS     — največ zaporednih dni (3 zaporedni = prepoved)
# Privzete vrednosti (2 / 1 / 3 / 2) dajo natanko dosedanje vedenje šole.

def _validate_razred(razred: str, config: SchoolConfig):
    """Preveri, ali razred obstaja v konfiguraciji ŠOLE."""
    if razred not in config.RAZREDI:
        raise HTTPException(status_code=400, detail="Neveljaven razred.")


def _get_week_start(d: date) -> date:
    """Vrne ponedeljek tedna za dan d (Python weekday(): 0=pon, 6=ned)."""
    return d - timedelta(days=d.weekday())


def _get_week_end(week_start: date) -> date:
    """Vrne nedeljo tedna."""
    return week_start + timedelta(days=6)


def _get_assessments_in_week(db: Session, school_id: int | None, razred: str, week_start: date) -> List[Assessment]:
    """Vrne vsa ocenjevanja za razred v danem tednu (pon–ned) znotraj šole."""
    week_end = _get_week_end(week_start)
    return scope(db.query(Assessment).filter(
        and_(
            Assessment.razred == razred,
            Assessment.date >= week_start,
            Assessment.date <= week_end
        )
    ), Assessment, school_id).all()


def _check_consecutive_days(dates: List[date], max_consecutive: int = 2) -> bool:
    """Preveri, ali je v seznamu preveč zaporednih dni.

    Primer (max_consecutive=2): [pon, tor, sre] → True (3 zaporedni so prepovedani).
    Primer (max_consecutive=2): [pon, sre, pet] → False (presledki).
    """
    if len(dates) < max_consecutive + 1:
        return False
    sorted_dates = sorted(dates)
    run = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            run += 1
            if run > max_consecutive:
                return True
        else:
            run = 1
    return False


def _check_weekly_limit(db: Session, config: SchoolConfig, school_id: int | None,
                        razred: str, nova_date: date, je_ponavljanje: bool):
    """Preveri tedenske omejitve za ocenjevanja (vrednosti iz nastavitev šole).

    Preveri:
    1. Največ ASSESSMENT_MAX_PER_DAY ocenjevanj na dan (privzeto 1)
    2. Največ ASSESSMENT_MAX_PER_WEEK običajnih ocenjevanj na teden (privzeto 2)
    3. Največ ASSESSMENT_MAX_PER_WEEK_WITH_RETAKE skupaj, ko je vmes
       ponavljanje (privzeto 3) — to je »izjema« za ponavljanje
    4. Prepoved več kot ASSESSMENT_MAX_CONSECUTIVE_DAYS zaporednih dni
       (privzeto 2 → 3 zaporedni dnevi so prepovedani)

    Zakaj so ta pravila v kodi in ne v bazi? Ker vključujejo tedenske
    izračune; v bazi pa so NASTAVITVE (meje), ki jih šolski admin
    prilagodi svojim pravilom.
    """
    week_start = _get_week_start(nova_date)
    week_end = _get_week_end(week_start)

    assessments = _get_assessments_in_week(db, school_id, razred, week_start)

    max_per_day = config.ASSESSMENT_MAX_PER_DAY
    max_per_week = config.ASSESSMENT_MAX_PER_WEEK
    max_with_retake = config.ASSESSMENT_MAX_PER_WEEK_WITH_RETAKE
    max_consecutive = config.ASSESSMENT_MAX_CONSECUTIVE_DAYS

    # 1) Največ N ocenjevanj na isti dan
    same_day = sum(1 for a in assessments if a.date == nova_date)
    if same_day >= max_per_day:
        if max_per_day == 1:
            raise HTTPException(
                status_code=400,
                detail="V istem tednu ne morete imeti dveh ocenjevanj na isti dan."
            )
        raise HTTPException(
            status_code=400,
            detail=f"Na ta dan je že {same_day} ocenjevanj (največ {max_per_day} na dan)."
        )

    normal_count = sum(1 for a in assessments if not a.ponavljanje)
    retake_count = sum(1 for a in assessments if a.ponavljanje)

    normal_after = normal_count + (0 if je_ponavljanje else 1)
    retake_after = retake_count + (1 if je_ponavljanje else 0)
    total_after = len(assessments) + 1

    # 2) Običajna ocenjevanja na teden
    if normal_after > max_per_week:
        detail = (
            f"V tem tednu ({week_start.strftime('%d.%m.%Y')}-{week_end.strftime('%d.%m.%Y')}) "
            f"sta že {normal_count} običajni ocenjevanji. "
            f"Maksimalno {max_per_week} običajni na teden."
        )
        raise HTTPException(status_code=400, detail=detail)

    # 3) Skupna meja za teden — višja, če je vmes ponavljanje
    week_cap = max_with_retake if retake_after > 0 else max_per_week
    if total_after > week_cap:
        detail = (
            f"V tem tednu ({week_start.strftime('%d.%m.%Y')}-{week_end.strftime('%d.%m.%Y')}) "
            f"so že {len(assessments)} ocenjevanja. Maksimalno {week_cap} na teden."
        )
        raise HTTPException(status_code=400, detail=detail)

    # 4) Prepoved preveč zaporednih dni
    vse_dates = [a.date for a in assessments] + [nova_date]
    if _check_consecutive_days(vse_dates, max_consecutive):
        raise HTTPException(
            status_code=400,
            detail=f"Ocenjevanja ne smejo biti na {max_consecutive + 1} zaporedne dni (npr. pon, tor, sre)."
        )


# ── Seznam ocenjevanj ──────────────────────────────────────────────────

@router.get("", response_model=List[AssessmentOut])
def list_ocenjevanja(
    request: Request,
    razred: Optional[str] = Query(None),
    month: Optional[str] = Query(None, description="Format: YYYY-MM"),
    db: Session = Depends(get_db)
):
    """Vrni seznam ocenjevanj z opcijskimi filtri.
    
    Filtriranje po razredu in/ali mesecu (YYYY-MM).
    Rezultati so urejeni po datumu in omejeni na šolo uporabnika.
    """
    school_id = data_school_id(request, db)
    config = config_for_request(request, db)
    query = scope(db.query(Assessment).options(joinedload(Assessment.teacher)), Assessment, school_id)
    
    if razred:
        _validate_razred(razred, config)
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


# ── Ustvarjanje ocenjevanja ───────────────────────────────────────────

@router.post("", response_model=AssessmentOut, status_code=201)
def create_ocenjevanje(data: AssessmentCreate, request: Request, db: Session = Depends(get_db)):
    """Ustvari novo ocenjevanje.
    
    POST /api/ocenjevanja
    
    Postopek:
    1. Validacija razreda
    2. Race condition zaščita (enako kot rezervacije)
    3. Preverjanje blokade (dan dejavnosti za razred → 400)
    4. Preverjanje tedenskih omejitev
    5. Shranjevanje
    
    Zakaj zavrnitev? Dan dejavnosti (zaseden datum) za razred pomeni,
    da razred ta dan ni na voljo za ocenjevanja — ocenjevanje se zavrne
    s 400 in jasnim sporočilom za učitelja.
    """
    config = config_for_request(request, db)
    _validate_razred(data.razred, config)

    # Datum ne sme biti v preteklosti (API validacija, UI to že prepreči).
    if data.date < date.today():
        raise HTTPException(status_code=400, detail="Datum ne sme biti v preteklosti.")
    
    school_id = write_school_id(request, db)

    # Get current user name
    user_id = get_current_user_id(request)
    current_user = db.query(User).filter(User.id == int(user_id)).first() if user_id else None
    user_name = f"{current_user.first_name} {current_user.last_name}".strip() if current_user else "?"
    
    # Resource key for race detection — vključuje šolo, da se ista ura v
    # dveh šolah ne šteje kot race condition.
    resource_key = f"school:{school_id}:ocenjevanje:{data.razred}:{data.date}"
    
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
        
        # Dan dejavnosti (zaseden datum) za ta razred → ocenjevanje ni dovoljeno.
        # Preveri se PRED ostalimi pravili, ker ima blokada prednost.
        blocked = db.query(BlockedDate).filter(
            BlockedDate.razred == data.razred,
            BlockedDate.date == data.date,
            BlockedDate.school_id == school_id,
        ).first()
        if blocked:
            raise HTTPException(
                status_code=400,
                detail=f"Za razred {data.razred} je {data.date.strftime('%d.%m.%Y')} dan dejavnosti — ocenjevanje na ta dan ni mogoče."
            )

        # Check weekly limits
        _check_weekly_limit(db, config, school_id, data.razred, data.date, data.ponavljanje)

        # Varnost: teacher_id vedno iz seje, NIKOLI od clienta (prepreči
        # spoofing — ustvarjanje ocenjevanja v imenu drugega učitelja).
        payload = data.model_dump()
        payload["teacher_id"] = current_user.id if current_user else None
        payload["school_id"] = school_id
        assessment = Assessment(**payload)
        db.add(assessment)
        try:
            db.commit()
            db.refresh(assessment)
        except Exception:
            db.rollback()
            raise HTTPException(status_code=500, detail="Napaka pri shranjevanju ocenjevanja")
        
        cleanup(resource_key)
        log_audit(db, user_id=get_current_user_id(request) or 0, username=user_name,
                  action="create_ocenjevanje",
                  details=f"razred={data.razred}, date={data.date}, ponavljanje={data.ponavljanje}",
                  school_id=school_id)
        return assessment


# ── CSV izvoz ocenjevanj ─────────────────────────────────────────────

@router.get("/export/csv")
def export_ocenjevanja_csv(
    request: Request,
    razred: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Izvozi ocenjevanja v CSV. Samo admin in vodstvo.
    
    CSV vsebuje: Datum, Razred, Tip (Ponavljanje/Običajno), Učitelj, ID.
    """
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or role_value(user) not in (RoleEnum.admin.value, RoleEnum.vodstvo.value):
        raise HTTPException(status_code=403, detail="Samo admin in vodstvo lahko izvažata CSV.")

    school_id = data_school_id(request, db)
    config = config_for_request(request, db)
    query = scope(db.query(Assessment).options(joinedload(Assessment.teacher)), Assessment, school_id)
    if razred:
        _validate_razred(razred, config)
        query = query.filter(Assessment.razred == razred)
    rows = query.order_by(Assessment.date, Assessment.razred).all()

    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Datum", "Razred", "Tip", "Ucitelj", "ID"])
    for a in rows:
        teacher_name = ""
        if a.teacher:
            full = f"{a.teacher.first_name} {a.teacher.last_name}".strip()
            teacher_name = full if full else a.teacher.username
        tip = "Ponavljanje" if a.ponavljanje else "Običajno"
        writer.writerow([a.date, a.razred, tip, teacher_name, a.id])

    from fastapi.responses import StreamingResponse
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=ocenjevanja_{razred or 'vsi'}.csv"},
    )


# ── Brisanje ocenjevanja ─────────────────────────────────────────────

@router.delete("/{id}")
def delete_ocenjevanje(id: int, request: Request, db: Session = Depends(get_db)):
    """Izbriši ocenjevanje.
    
    Pravice: avtor, admin ali vodstvo.
    Beležimo v audit log.
    """
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    
    current_user = db.query(User).filter(User.id == int(user_id)).first()
    if not current_user:
        raise HTTPException(status_code=401, detail="Uporabnik ne obstaja")
    
    # Iskanje omejeno na šolo uporabnika (prepreči brisanje tujih zapisov).
    school_id = data_school_id(request, db)
    assessment = scope(
        db.query(Assessment).filter(Assessment.id == id), Assessment, school_id
    ).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Ocenjevanje ne obstaja")
    
    # Only the creator, admin or vodstvo can delete
    if assessment.teacher_id != current_user.id and role_value(current_user) not in (RoleEnum.admin.value, RoleEnum.vodstvo.value):
        raise HTTPException(status_code=403, detail="Samo avtor, admin ali vodstvo lahko briše ocenjevanje")
    
    user_name = f"{current_user.first_name} {current_user.last_name}".strip() or current_user.username
    log_audit(
        db, current_user.id, user_name, "delete_ocenjevanje",
        f"Izbrisano ocenjevanje: {assessment.razred}, {assessment.date}",
        school_id=assessment.school_id,
    )

    db.delete(assessment)
    db.commit()
    return {"message": "Ocenjevanje izbrisano"}
