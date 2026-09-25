# ─────────────────────────────────────────────────────────────────────────
# app/subscriptions.py — naročnine šol (mesečna uporaba)
#
# Pravilo (zahteva uporabnika 2026-09-25):
#   * vsaka šola ima v bazi DATUM VELJAVNOSTI naročnine (school_settings,
#     ključ NAROCNINA_DO);
#   * dokler je datum v prihodnosti, šola normalno uporablja aplikacijo;
#   * ko poteče (ali če ga šola sploh nima), aplikacija za to šolo ni več
#     dostopna — PRIJAVI SE LAHKO VEDNO SAMO ŠOLSKI ADMIN (in glavni admin),
#     ki ima v nastavitvah možnost nakupa za en mesec;
#   * ko je prodaja v tej namestitvi izklopljena (privzeto, npr. v šoli na k3s),
#     preverjanja NI — aplikacija deluje kot prej.
# ─────────────────────────────────────────────────────────────────────────

import calendar
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.app_settings import selling_enabled
from app.tenancy import get_school_config, set_school_setting

KEY_VALID_UNTIL = "NAROCNINA_DO"


def _parse_day(value) -> date | None:
    """Pretvori shranjeno besedilo (ISO datum) v date; neveljavno → None."""
    if isinstance(value, date):
        return value
    text = (str(value) if value is not None else "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def get_valid_until(db: Session, school_id: int) -> date | None:
    """Datum veljavnosti naročnine za šolo (None = ni kupljena)."""
    return _parse_day(get_school_config(db, school_id).get_str(KEY_VALID_UNTIL, ""))


def set_valid_until(db: Session, school_id: int, day: date | None) -> None:
    """Nastavi datum veljavnosti (None → izbriše)."""
    set_school_setting(db, school_id, KEY_VALID_UNTIL, day.isoformat() if day else "")


def _add_months(day: date, months: int) -> date:
    """Dodaj mesece; če dan v ciljnem mesecu ne obstaja, vzemi zadnji dan meseca."""
    index = day.month - 1 + months
    year = day.year + index // 12
    month = index % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last))


def days_left(db: Session, school_id: int) -> int | None:
    """Koliko dni veljavnosti je še (None = naročnine ni; negativno = potekla)."""
    until = get_valid_until(db, school_id)
    if until is None:
        return None
    return (until - date.today()).days


def maybe_expired(db: Session, school_id: int) -> bool:
    """Ali je naročnina te šole potekla (oziroma je sploh ni)?"""
    until = get_valid_until(db, school_id)
    return until is None or until < date.today()


def is_active(db: Session, school_id: int) -> bool:
    """Ali šola lahko uporablja aplikacijo?

    Če prodaja v tej namestitvi ni vklopljena, je odgovor VEDNO True (šolska
    namestitev se po posodobitvi ne obnaša nič drugače kot prej).
    """
    if not selling_enabled(db):
        return True
    return not maybe_expired(db, school_id)


def extend_subscription(db: Session, school_id: int, months: int = 1) -> date:
    """Podaljšaj naročnino za `months` mesecev in vrni nov datum veljavnosti.

    Podaljšuje se od TRENUTNEGA datuma veljavnosti, če ta še ni potekel (da šola
    ne izgubi že plačanih dni), sicer od danes.
    """
    today = date.today()
    current = get_valid_until(db, school_id)
    base = current if current and current > today else today
    new_until = _add_months(base, max(1, int(months)))
    set_valid_until(db, school_id, new_until)
    return new_until


def subscription_state(db: Session, school_id: int) -> dict:
    """Stanje naročnine za predloge: prodaja, aktivnost, do kdaj, koliko dni."""
    until = get_valid_until(db, school_id)
    return {
        "selling": selling_enabled(db),
        "active": is_active(db, school_id),
        "until": until,
        "days_left": days_left(db, school_id),
    }
