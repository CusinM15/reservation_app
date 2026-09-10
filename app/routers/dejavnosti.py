# ─────────────────────────────────────────────────────────────────────────
# app/routers/dejavnosti.py — UI "Vnos dejavnosti" (dnevi dejavnosti)
#
# Namen: Vodstvo/admin vizualno upravlja vse daljše dejavnosti (kulturni,
# naravoslovni, tehniški, športni dnevi) po razredih, s CRUD po vrsticah.
#
# Kaj ta router dela:
#   1. CRUD za tabelo activity_days (vsaka vrstica = ena dejavnost).
#   2. Ob shranjevanju z izpolnjenim datumom, full_day in prostori
#      sinhronizira z obstoječim modelom:
#        - ustvari BlockedDate za izbrane razrede/datume (dan dejavnosti)
#        - izbriše ocenjevanja za te razrede/datume + email učiteljem
#        - ustvari serijske rezervacije prostorov za ure 1–5
#   3. Uvoz iz Excel predloge (dnevi_dejavnosti_v_evrih.xlsx) — listi po razredih.
#
# Pravice: SAMO vodstvo/admin (in obstoječi ALLOWED_USER_IDS iz blocked_dates).
# Učitelji te strani ne vidijo; posledice (blokade, rezervacije, preklini
# ocenjevanj, emaili) so vidne vsem.
# ─────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActivityDay, BlockedDate, Assessment, User, RoleEnum, Reservation
from app.schemas import ActivityDayCreate, ActivityDayOut
from app.config import settings
from app.audit import log_audit
from app.security import get_current_user_id
from app.routers.blocked_dates import _send_email

router = APIRouter(prefix="/api/dejavnosti", tags=["dejavnosti"])

SECTIONS = ["KULTURNI", "NARAVOSLOVNI", "TEHNIŠKI", "ŠPORTNI"]
HOURS_FULLDAY = [1, 2, 3, 4, 5]  # 1.–5. ura (ne predura 0)
ALLOWED_USER_IDS = {1, 2, 3, 4}  # enako kot blocked_dates


def _check_allowed(user_id, db: Session) -> int:
    uid = int(user_id) if user_id is not None else -1
    if uid in ALLOWED_USER_IDS:
        return uid
    user = db.query(User).filter(User.id == uid).first()
    if user and user.role in (RoleEnum.admin, RoleEnum.vodstvo):
        return uid
    raise HTTPException(status_code=403, detail="Nimate pravic za upravljanje dejavnosti")


def _resolve_letter_oddelki(grade: str, all_razredi: list[str]) -> list[str]:
    """Vrni vse črkovne oddelke generacije (1.a..1.c, ...), izpusti številčne."""
    return [r for r in all_razredi
            if r.startswith(f"{grade}.") and re.match(r"^\d+\.[a-zč]$", r)]


def _split_csv(s: str | None) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def _apply_sync(db: Session, data: ActivityDayCreate, user):
    """Ustvari blokade + rezervacije + prekli z obstoječimi podatki.

    Izvede se le, ko je datum determiniran (date_from), full_day in so izbrani
    razredi. Vrne dict s statistiko (blocked, deleted_assessments, emails,
    reservations), sicer prazno statistiko.
    """
    if not data.date_from:
        return {"blocked": 0, "deleted_assessments": 0, "emails_sent": 0, "reservations": 0}
    if not data.full_day:
        return {"blocked": 0, "deleted_assessments": 0, "emails_sent": 0, "reservations": 0}

    date_to = data.date_to or data.date_from
    if date_to < data.date_from:
        raise HTTPException(status_code=400, detail="Končni datum mora biti po začetnem")

    # Razredi
    if data.all_classes:
        oddelki = _resolve_letter_oddelki(data.grade, settings.RAZREDI)
    else:
        oddelki = _split_csv(data.classes)
    oddelki = [o for o in oddelki if o in settings.RAZREDI]
    if not oddelki:
        return {"blocked": 0, "deleted_assessments": 0, "emails_sent": 0, "reservations": 0}

    creator_name = f"{user.first_name} {user.last_name}".strip() or user.username
    stat = {"blocked": 0, "deleted_assessments": 0, "emails_sent": 0, "reservations": 0}

    # 1) BlockedDate za vsak delovnik v obsegu in vsak razred + preklic ocenjevanj
    cur = data.date_from
    while cur <= date_to:
        if cur.weekday() < 5:
            for odd in oddelki:
                exists = db.query(BlockedDate).filter(
                    BlockedDate.razred == odd, BlockedDate.date == cur).first()
                if not exists:
                    db.add(BlockedDate(razred=odd, date=cur, created_by_id=user.id))
                    stat["blocked"] += 1
                # preklic ocenjevanj
                for a in db.query(Assessment).filter(
                        Assessment.razred == odd, Assessment.date == cur).all():
                    teacher = db.query(User).filter(User.id == a.teacher_id).first()
                    log_audit(db, user.id, creator_name, "delete_assessment",
                              f"Avtomatsko izbrisano ocenjevanje (dejavnost): {odd}, {cur}")
                    db.delete(a)
                    stat["deleted_assessments"] += 1
                    if teacher and teacher.email:
                        ds = cur.strftime("%d.%m.%Y")
                        _send_email(
                            to_email=teacher.email,
                            subject=f"Ocenjevanje za {odd} na dan {ds} prestavljeno",
                            body=f"Pozdravljeni,\n\n{creator_name} je razred {odd} na dan {ds} "
                                 f"označil(a) kot dan dejavnosti, zato je bilo vaše ocenjevanje "
                                 f"za ta dan samodejno preklicano. Prosimo, da izberete nov datum.\n\n"
                                 f"Lep pozdrav,\nŠolski App")
                        stat["emails_sent"] += 1
        cur += timedelta(days=1)

    # 2) Rezervacije prostorov (ure 1–5) za vsak izbran prostor in delovnik
    title = (data.title or "").strip() or f"{data.section} {data.grade}. razred"
    import uuid
    prostori = _split_csv(data.prostori)
    for prostor in prostori:
        if prostor not in settings.PROSTORI:
            continue
        series_id = str(uuid.uuid4())
        d = data.date_from
        while d <= date_to:
            if d.weekday() < 5:
                for h in HOURS_FULLDAY:
                    db.add(Reservation(
                        prostor=prostor, date=d, hour=h,
                        teacher_id=user.id, qty=None,
                        series_id=series_id, name=title,
                    ))
                    stat["reservations"] += 1
            d += timedelta(days=1)

    db.commit()
    return stat


# ── Seznam dejavnosti (po razredu) ───────────────────────────────────

# Vrstni red sekcij mora slediti Excel predlogi: KULTURNI → NARAVOSLOVNI
# → TEHNIŠKI → ŠPORTNI. Privzeti lexikografski ORDER BY section bi dal
# TEHNIŠKI za ŠPORTNIM (Š < T), zato uporabimo eksplicitno prioriteto.
_SECTION_ORDER = {"KULTURNI": 0, "NARAVOSLOVNI": 1, "TEHNIŠKI": 2, "ŠPORTNI": 3}


@router.get("", response_model=list[ActivityDayOut])
def list_dejavnosti(
    grade: Optional[str] = Query(None),
    section: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(ActivityDay)
    if grade:
        query = query.filter(ActivityDay.grade == grade)
    if section:
        query = query.filter(ActivityDay.section == section)
    if source:
        query = query.filter(ActivityDay.source == source)
    from sqlalchemy import case
    section_priority = case(
        {k: v for k, v in _SECTION_ORDER.items()},
        value=ActivityDay.section,
        else_=99,
    )
    query = query.order_by(section_priority, ActivityDay.id)
    return query.all()


# ── Izpis konfiguracije za UI (samo vodstvo/admin) ──────────────────

@router.get("/meta")
def dejavnosti_meta(request: Request, db: Session = Depends(get_db)):
    """Vrni razrede, prostore, sekcije in vse razpoložljive grade-e."""
    _check_allowed(get_current_user_id(request), db)
    # Razredi 1..9 so "dnevi dejavnosti" (iz xlsx). IP/POUK je en sam zavíhek.
    grades = [str(i) for i in range(1, 10)] + ["ip"]
    return {
        "grades": grades,
        "razredi": settings.RAZREDI,
        "prostori": settings.PROSTORI,
        "sections": SECTIONS,
        "razpored": settings.SCHEDULE,
    }


# ── Ustvarjanje ────────────────────────────────────────────────────

@router.post("", response_model=ActivityDayOut, status_code=201)
def create_dejavnost(data: ActivityDayCreate, request: Request, db: Session = Depends(get_db)):
    uid = _check_allowed(get_current_user_id(request), db)
    user = db.query(User).filter(User.id == uid).first()
    is_num = data.grade.isdigit() and 1 <= int(data.grade) <= 9
    if is_num and data.section not in SECTIONS:
        raise HTTPException(status_code=400, detail=f"Neveljavna sekcija: {data.section}")
    stat = _apply_sync(db, data, user)
    title = (data.title or "").strip() or f"{data.section} {data.grade}. razred"
    source = data.source if data.source in ("xlsx", "manual") else "manual"
    rec = ActivityDay(
        grade=data.grade, section=data.section, title=title,
        subtitle=data.subtitle or "", full_day=data.full_day, recurring=data.recurring,
        date_from=data.date_from, date_to=data.date_to,
        date_undetermined=data.date_undetermined, date_text=data.date_text or "",
        all_classes=data.all_classes, classes=data.classes or "",
        prostori=data.prostori or "", cena=data.cena or "", vodja=data.vodja or "",
        opomba=data.opomba or "", created_by_id=user.id, source=source,
        parent_title=(data.parent_title or "").strip(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    log_audit(db, user.id, f"{user.first_name} {user.last_name}".strip(),
              "create_dejavnost",
              f"grade={data.grade}, section={data.section}, title={title}, source={source}, "
              f"sync={stat}")
    return rec


# ── Posodobitev ────────────────────────────────────────────────────

@router.put("/{dej_id}", response_model=ActivityDayOut)
def update_dejavnost(dej_id: int, data: ActivityDayCreate, request: Request, db: Session = Depends(get_db)):
    uid = _check_allowed(get_current_user_id(request), db)
    user = db.query(User).filter(User.id == uid).first()
    rec = db.query(ActivityDay).filter(ActivityDay.id == dej_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Dejavnost ne obstaja")
    is_num = data.grade.isdigit() and 1 <= int(data.grade) <= 9
    if is_num and data.section not in SECTIONS:
        raise HTTPException(status_code=400, detail=f"Neveljavna sekcija: {data.section}")
    stat = _apply_sync(db, data, user)
    title = (data.title or "").strip() or f"{data.section} {data.grade}. razred"
    rec.grade = data.grade
    rec.section = data.section
    rec.title = title
    rec.subtitle = data.subtitle or ""
    rec.full_day = data.full_day
    rec.recurring = data.recurring
    rec.date_from = data.date_from
    rec.date_to = data.date_to
    rec.date_undetermined = data.date_undetermined
    rec.date_text = data.date_text or ""
    rec.all_classes = data.all_classes
    rec.classes = data.classes or ""
    rec.prostori = data.prostori or ""
    rec.cena = data.cena or ""
    rec.vodja = data.vodja or ""
    rec.opomba = data.opomba or ""
    rec.parent_title = (data.parent_title or "").strip()
    db.commit()
    db.refresh(rec)
    log_audit(db, user.id, f"{user.first_name} {user.last_name}".strip(),
              "update_dejavnost", f"id={dej_id}, sync={stat}")
    return rec


# ── Brisanje ───────────────────────────────────────────────────────

@router.delete("/{dej_id}")
def delete_dejavnost(dej_id: int, request: Request, db: Session = Depends(get_db)):
    uid = _check_allowed(get_current_user_id(request), db)
    user = db.query(User).filter(User.id == uid).first()
    rec = db.query(ActivityDay).filter(ActivityDay.id == dej_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Dejavnost ne obstaja")
    log_audit(db, user.id, f"{user.first_name} {user.last_name}".strip(),
              "delete_dejavnost",
              f"id={dej_id}, grade={rec.grade}, section={rec.section}, title={rec.title}")
    db.delete(rec)
    db.commit()
    return {"message": "Dejavnost izbrisana"}

