# ─────────────────────────────────────────────────────────────────────────
# app/school_year.py — samodejni izbris podatkov preteklega šolskega leta
#
# Zahteva uporabnika 2026-11-05: prvega septembra se samodejno izbrišejo
# VSE rezervacije in napovedana ocenjevanja ZA NAZAJ (iz preteklega šolskega
# leta). Dnevi dejavnosti (activity_days) OSTAJEJO — zato je za novo leto
# treba urediti zgolj datume, saj so dejavnosti iz leta v leto večinoma enake.
#
# Meja: 1. september tekočega šolskega leta. Podatki s datumom PRED mejo so
# "za nazaj" in se izbrišejo; novejši (tekoče/prihodnje leto) ostanejo.
# ─────────────────────────────────────────────────────────────────────────

from datetime import date

from sqlalchemy.orm import Session

from app.app_settings import get_app_setting, set_app_setting
from app.models import Assessment, Reservation

# Marker: leto cut-offa, za katero je bil purge že izveden (enkrat na šolsko leto).
KEY_PURGE_YEAR = "PURGE_SCHOOL_YEAR"


def school_year_cutoff(today: date | None = None) -> date:
    """Vrni 1. september tekočega šolskega leta (meja za "za nazaj").

    Primeri: 1. 9. 2026 → 1. 9. 2026; 15. 10. 2026 → 1. 9. 2026;
    1. 3. 2027 → 1. 9. 2026 (šolsko leto se je začelo septembra 2026).
    """
    d = today or date.today()
    year = d.year if (d.month, d.day) >= (9, 1) else d.year - 1
    return date(year, 9, 1)


def purge_previous_school_year(db: Session, today: date | None = None) -> dict:
    """Izbriši rezervacije in ocenjevanja s datumom pred 1. 9. tekočega šolskega leta.

    Idempotentno: izvede se enkrat na šolsko leto (marker v app_settings).
    Dnevi dejavnosti ostanejo. Vrne slovar s števili izbrisanih zapisov.
    """
    cutoff = school_year_cutoff(today)
    marker = get_app_setting(db, KEY_PURGE_YEAR, "")
    if marker == str(cutoff.year):
        return {
            "cutoff": cutoff.isoformat(),
            "reservations": 0,
            "assessments": 0,
            "skipped": True,
        }

    n_res = (
        db.query(Reservation)
        .filter(Reservation.date < cutoff)
        .delete(synchronize_session=False)
    )
    n_ass = (
        db.query(Assessment)
        .filter(Assessment.date < cutoff)
        .delete(synchronize_session=False)
    )
    set_app_setting(db, KEY_PURGE_YEAR, str(cutoff.year))
    db.commit()
    return {
        "cutoff": cutoff.isoformat(),
        "reservations": n_res,
        "assessments": n_ass,
        "skipped": False,
    }
