# ─────────────────────────────────────────────────────────────────────────
# app/routers/blocked_dates.py — Upravljanje dni dejavnosti
#
# Namen: Omogoča admin/vodstvu, da označi določene datume kot "zasedene"
# za posamezne razrede. To pomeni, da na ta dan ni možno napovedati
# ocenjevanja (obstoječa se avtomatsko izbrišejo).
#
# Zakaj zasedeni datumi?
# Šola ima pogosto dneve, ko so razredi zasedeni (ekskurzije, športni
# dnevi, kulturni dnevi, naravoslovni dnevi, tekmovanja, itd.). Namesto
# da vsak učitelj posebej išče te informacije, vodstvo označi datum
# kot zaseden in vsa ocenjevanja se samodejno prestavijo.
#
# Kako deluje?
# 1. Vodstvo/admin pošlje zahtevek z razredi in datumskim razponom.
# 2. Za vsak dan v razponu (razen vikendov) se ustvari BlockedDate zapis.
# 3. Če obstajajo ocenjevanja za te razrede na te datume, se izbrišejo.
# 4. Učitelji dobijo email obvestilo o preklicu.
#
# Omejitev: Samo uporabniki z ID {1, 2, 3, 4} ali vloga admin/vodstvo.
# ─────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from datetime import date, timedelta
from typing import List, Optional
from pydantic import BaseModel
import smtplib, ssl
from email.mime.text import MIMEText
from calendar import monthrange

from app.database import get_db
from app.models import BlockedDate, User, Assessment, RoleEnum
from app.config import settings
from app.audit import log_audit
from app.security import get_current_user_id
from app.tenancy import (
    config_for_request,
    data_school_id,
    scope,
    write_school_id,
)

router = APIRouter(prefix="/api/blocked-dates", tags=["blocked-dates"])

ALLOWED_USER_IDS = {1, 2, 3, 4}  # admin, Gaber, Mateja, Sanela


class BlockedDatesCreate(BaseModel):
    """Vhodni podatki za blokiranje datumov za več razredov v razponu."""
    razredi: List[str]
    date_from: date
    date_to: date


class BlockedDateOut(BaseModel):
    """Izhodni podatki za zaseden datum."""
    id: int
    razred: str
    date: date
    created_by_id: int

    model_config = {"from_attributes": True}


# ── Preverjanje pravic ────────────────────────────────────────────────
# Zakaj tudi ALLOWED_USER_IDS? Ker so bili nekateri uporabniki (Gaber,
# Mateja, Sanela) dodani pred implementacijo vlog. Namesto migracije
# podatkov, smo dodali ekspliciten set ID-jev. To je začasna rešitev
# in bi jo morali zamenjati s preverjanjem vlog.
def _check_allowed(user_id, db: Session):
    uid = int(user_id) if user_id is not None else -1
    if uid in ALLOWED_USER_IDS:
        return uid
    user = db.query(User).filter(User.id == uid).first()
    if user and user.role in (RoleEnum.admin, RoleEnum.vodstvo):
        return uid
    raise HTTPException(status_code=403, detail="Nimate pravic za upravljanje dni dejavnosti")


# ── Pošiljanje emailov ────────────────────────────────────────────────
# Ločena funkcija za pošiljanje emailov, ker jo uporabljajo tudi drugi
# routerji (auth, rezervacije, dejavnosti). Če MAIL_PASSWORD ni nastavljen,
# se emaili ne pošiljajo (tiho ignoriranje napak).
#
# config: SchoolConfig — nastavitve šole, iz katere naj gre pošta (SMTP
# strežnik, pošiljatelj). Če ni podan, se uporabijo vrednosti iz .env
# (zato starim klicem ni treba nič spremeniti).
def _send_email(to_email: str, subject: str, body: str, config=None):
    """Pošlji email preko SMTP šole. Best-effort — napake se ignorirajo."""
    server = config.MAIL_SERVER if config is not None else settings.MAIL_SERVER
    port = config.MAIL_PORT if config is not None else settings.MAIL_PORT
    sender = config.MAIL_FROM if config is not None else settings.MAIL_FROM
    username = config.MAIL_USERNAME if config is not None else settings.MAIL_USERNAME
    password = config.MAIL_PASSWORD if config is not None else settings.MAIL_PASSWORD
    if not password or not to_email:
        return
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email
        context = ssl.create_default_context()
        with smtplib.SMTP(server, port) as s:
            s.starttls(context=context)
            s.login(username, password)
            s.send_message(msg)
    except Exception:
        pass  # best-effort


# ── Seznam zasedenih datumov ─────────────────────────────────────────

@router.get("", response_model=List[BlockedDateOut])
def list_blocked_dates(
    request: Request,
    month: Optional[str] = Query(None, description="Format: YYYY-MM"),
    db: Session = Depends(get_db)
):
    """Vrni seznam zasedenih datumov za določen mesec (ali vse).

    Vrne samo datume šole trenutnega uporabnika (izolacija med šolami).
    """
    school_id = data_school_id(request, db)
    query = scope(db.query(BlockedDate), BlockedDate, school_id)
    if month:
        try:
            year, month_num = map(int, month.split('-'))
            start_date = date(year, month_num, 1)
            last_day = monthrange(year, month_num)[1]
            end_date = date(year, month_num, last_day)
            query = query.filter(
                BlockedDate.date >= start_date,
                BlockedDate.date <= end_date
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Neveljaven format meseca")
    return query.order_by(BlockedDate.date).all()


# ── Ustvarjanje zasedenih datumov ─────────────────────────────────────

@router.post("", status_code=201)
def create_blocked_dates(
    data: BlockedDatesCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Ustvari zasedene datume za več razredov v datumskem razponu.
    
    Za vsak dan v razponu (brez vikendov) in za vsak razred:
    1. Preskoči, če že obstaja BlockedDate za ta (razred, datum).
    2. Ustvari nov BlockedDate.
    3. Poišči in izbriši vsa ocenjevanja za ta (razred, datum).
    4. Pošlji email učitelju, če je obstajalo ocenjevanje.
    
    To je idempotentna operacija — če datum že obstaja, se preskoči.
    """
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    uid = _check_allowed(user_id, db)
    school_id = write_school_id(request, db)
    config = config_for_request(request, db)
    creator = db.query(User).filter(User.id == uid).first()
    creator_name = f"{creator.first_name} {creator.last_name}".strip() or creator.username

    if data.date_to < data.date_from:
        raise HTTPException(status_code=400, detail="Končni datum mora biti po začetnem")

    created_count = 0
    deleted_assessments = 0
    emails_sent = 0

    current = data.date_from
    while current <= data.date_to:
        if current.weekday() >= 5:  # skip weekends
            current += timedelta(days=1)
            continue

        for razred in data.razredi:
            # Skip if already blocked (znotraj iste šole)
            existing = db.query(BlockedDate).filter(
                BlockedDate.razred == razred,
                BlockedDate.date == current,
                BlockedDate.school_id == school_id,
            ).first()
            if existing:
                continue

            bd = BlockedDate(razred=razred, date=current, created_by_id=uid, school_id=school_id)
            db.add(bd)
            created_count += 1

            # Find and delete assessments for this class on this date
            assessments = db.query(Assessment).filter(
                Assessment.razred == razred,
                Assessment.date == current,
                Assessment.school_id == school_id,
            ).all()
            for a in assessments:
                teacher = db.query(User).filter(User.id == a.teacher_id).first()
                log_audit(
                    db, uid, creator_name, "delete_assessment",
                    f"Avtomatsko izbrisano ocenjevanje (dan dejavnosti): {razred}, {current}",
                    school_id=school_id,
                )
                db.delete(a)
                deleted_assessments += 1

                # Send email to teacher
                if teacher and teacher.email:
                    date_str = current.strftime("%d.%m.%Y")
                    _send_email(
                        to_email=teacher.email,
                        subject=f"Ocenjevanje za {razred} na dan {date_str} prestavljeno",
                        body=f"Pozdravljeni,\n\n"
                             f"{creator_name} je razred {razred} na dan {date_str} označil(a) kot dan dejavnosti, "
                             f"zato je bilo vaše ocenjevanje za ta dan samodejno preklicano. "
                             f"Prosimo, da izberete nov datum.\n\n"
                             f"Lep pozdrav,\nŠolski App",
                        config=config,
                    )
                    emails_sent += 1

        current += timedelta(days=1)

    db.commit()
    log_audit(db, user_id=uid, username=f"{creator.first_name} {creator.last_name}".strip() or "?",
              action="create_blocked_dates",
              details=f"razredi={data.razredi}, date_from={data.date_from}, date_to={data.date_to}, created={created_count}, deleted_assessments={deleted_assessments}",
              school_id=school_id)
    return {
        "message": f"Dodanih {created_count} dni dejavnosti",
        "deleted_assessments": deleted_assessments,
        "emails_sent": emails_sent,
    }


# ── Brisanje zasedenega datuma ───────────────────────────────────────

@router.delete("/{id}")
def delete_blocked_date(
    id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Izbriši zaseden datum (samo admin/vodstvo).
    
    To omogoča, da se datum ponovno sprosti za ocenjevanja.
    Ne obnovi avtomatsko prej pobrisanih ocenjevanj — to mora
    učitelj storiti ročno.
    """
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    uid = _check_allowed(user_id, db)
    school_id = data_school_id(request, db)
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=401, detail="Uporabnik ne obstaja")

    # Iskanje je omejeno na šolo uporabnika (šolski admin ne more brisati
    # dni dejavnosti druge šole).
    bd = scope(
        db.query(BlockedDate).filter(BlockedDate.id == id), BlockedDate, school_id
    ).first()
    if not bd:
        raise HTTPException(status_code=404, detail="Dan dejavnosti ne obstaja")
    user_name = f"{user.first_name} {user.last_name}".strip() or user.username
    log_audit(
        db, user_id=user.id, username=user_name, action="delete_blocked_date",
        details=f"Odstranjen dan dejavnosti: {bd.razred}, {bd.date}",
        school_id=bd.school_id,
    )
    db.delete(bd)
    db.commit()
    return {"message": "Dan dejavnosti odstranjen."}
