# ─────────────────────────────────────────────────────────────────────────
# app/routers/blocked_dates.py — Upravljanje zasedenih datumov
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
    raise HTTPException(status_code=403, detail="Nimate pravic za upravljanje zasedenih datumov")


# ── Pošiljanje emailov ────────────────────────────────────────────────
# Ločena funkcija za pošiljanje emailov, ker jo uporabljajo tudi drugi
# routerji (auth, rezervacije). Če MAIL_PASSWORD ni nastavljen, se emaili
# ne pošiljajo (tiho ignoriranje napak).
def _send_email(to_email: str, subject: str, body: str):
    """Pošlji email preko Arnes SMTP. Best-effort — napake se ignorirajo."""
    if not settings.MAIL_PASSWORD or not to_email:
        return
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.MAIL_FROM
        msg["To"] = to_email
        context = ssl.create_default_context()
        with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as s:
            s.starttls(context=context)
            s.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            s.send_message(msg)
    except Exception:
        pass  # best-effort


# ── Seznam zasedenih datumov ─────────────────────────────────────────

@router.get("", response_model=List[BlockedDateOut])
def list_blocked_dates(
    month: Optional[str] = Query(None, description="Format: YYYY-MM"),
    db: Session = Depends(get_db)
):
    """Vrni seznam zasedenih datumov za določen mesec (ali vse)."""
    query = db.query(BlockedDate)
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
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    uid = _check_allowed(user_id, db)
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
            # Skip if already blocked
            existing = db.query(BlockedDate).filter(
                BlockedDate.razred == razred,
                BlockedDate.date == current
            ).first()
            if existing:
                continue

            bd = BlockedDate(razred=razred, date=current, created_by_id=uid)
            db.add(bd)
            created_count += 1

            # Find and delete assessments for this class on this date
            assessments = db.query(Assessment).filter(
                Assessment.razred == razred,
                Assessment.date == current
            ).all()
            for a in assessments:
                teacher = db.query(User).filter(User.id == a.teacher_id).first()
                log_audit(
                    db, uid, creator_name, "delete_assessment",
                    f"Avtomatsko izbrisano ocenjevanje (zaseden datum): {razred}, {current}"
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
                             f"{creator_name} je razred {razred} na dan {date_str} označil(a) kot zasedenega, "
                             f"zato je bilo vaše ocenjevanje za ta dan samodejno preklicano. "
                             f"Prosimo, da izberete nov datum.\n\n"
                             f"Lep pozdrav,\nŠolski App"
                    )
                    emails_sent += 1

        current += timedelta(days=1)

    db.commit()
    log_audit(db, user_id=uid, username=f"{creator.first_name} {creator.last_name}".strip() or "?",
              action="create_blocked_dates",
              details=f"razredi={data.razredi}, date_from={data.date_from}, date_to={data.date_to}, created={created_count}, deleted_assessments={deleted_assessments}")
    return {
        "message": f"Dodanih {created_count} zasedenih datumov",
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
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Niste prijavljeni")
    uid = _check_allowed(user_id, db)
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=401, detail="Uporabnik ne obstaja")

    bd = db.query(BlockedDate).filter(BlockedDate.id == id).first()
    if not bd:
        raise HTTPException(status_code=404, detail="Zaseden datum ne obstaja")
    user_name = f"{user.first_name} {user.last_name}".strip() or user.username
    log_audit(
        db, user_id=user.id, username=user_name, action="delete_blocked_date",
        details=f"Odstranjen zaseden datum: {bd.razred}, {bd.date}"
    )
    db.delete(bd)
    db.commit()
    return {"message": "Zaseden datum odstranjen."}
