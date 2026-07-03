# ─────────────────────────────────────────────────────────────────────────
# app/schemas.py — Pydantic sheme za API (validacija vhodnih/izhodnih podatkov)
#
# Namen: Definira oblike podatkov, ki jih API sprejema in vrača.
# Pydantic poskrbi za validacijo (npr. ura mora biti med 0 in 7).
#
# Zakaj ločeni schemas od modelov? Ker modeli odražajo DB strukturo,
# schemas pa API pogodbo. To nam omogoča, da API vrača drugačne podatke
# od DB (npr. teacher_name, ki je izračunan iz relacije).
# ─────────────────────────────────────────────────────────────────────────

from pydantic import BaseModel, Field
from datetime import date
from typing import Optional


# ── Rezervacije ─────────────────────────────────────────────────────

class ReservationCreate(BaseModel):
    """Vhodni podatki za ustvarjanje nove rezervacije.
    
    hour je omejen na 0–7 (šolske ure).
    qty je obvezno samo za 'tablice' (preverja se v routerju).
    razred je neobvezen — rezervacija je lahko brez razreda (npr. za sestanek).
    """
    date: date
    hour: int = Field(..., ge=0, le=7)
    prostor: str
    razred: Optional[str] = None
    teacher_id: int
    qty: Optional[int] = None


class ReservationOut(BaseModel):
    """Izhodni podatki za rezervacijo — kar API vrača.
    
    teacher_name se zapolni v routerju (joined load iz tabele User).
    series_id je prisoten samo za serijske rezervacije.
    
    model_config omogoča, da Pydantic bere direktno iz SQLAlchemy objektov.
    """
    id: int
    date: date
    hour: int
    prostor: str
    razred: Optional[str] = None
    teacher_id: int
    qty: Optional[int] = None
    teacher_name: Optional[str] = None  # filled by query join
    series_id: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Serijske rezervacije (samo admin/vodstvo) ──────────────────────────
# Te sheme so ločene, ker imajo serijske rezervacije drugačno logiko:
# namesto ene rezervacije ustvarijo več zapisov hkrati.

class WeeklySeriesCreate(BaseModel):
    """Rezerviraj isto uro vsak teden na isti dan v tednu, med date_from in date_to (vključno). Samo admin/vodstvo.
    
    Primer: vsak ponedeljek 1. uro v računalnici od 1.9. do 30.6.
    weekday = 0 (ponedeljek), hour = 0, date_from = 1.9., date_to = 30.6.
    """
    prostor: str
    hour: int = Field(..., ge=0, le=7)
    weekday: int = Field(..., ge=0, le=6, description="0=ponedeljek ... 6=nedelja (Python weekday())")
    date_from: date
    date_to: date
    qty: Optional[int] = None


class FullDaySeriesCreate(BaseModel):
    """Rezerviraj vse ure (0–7) za en ali več dni (npr. naravoslovni dan). Samo admin/vodstvo.
    
    Primer: cel dan v gospodinjstvu za 5. a (naravoslovni dan).
    hours lahko omejimo, npr. [0,1,2,3,4,5] za 6 ur namesto vseh 8.
    """
    prostor: str
    date_from: date
    date_to: date  # za en sam dan: date_from == date_to
    qty: Optional[int] = None
    hours: Optional[list[int]] = Field(
        default=None,
        description="Privzeto vse ure 0..7. Lahko se omeji npr. na [0,1,2,3,4,5] za 6 ur.",
    )


class SeriesResult(BaseModel):
    """Rezultat ustvarjanja serije — pove, kaj se je zgodilo.
    
    skipped vsebuje termine, ki so bili preskočeni (npr. prazniki).
    removed pove, koliko konfliktnih rezervacij je bilo avtomatsko pobrisanih.
    """
    series_id: str
    created: int
    skipped: list[dict] = Field(default_factory=list)  # [{date, hour, reason}]
    removed: int = 0  # število pobrisanih konfliktnih rezervacij


class SeriesListItem(BaseModel):
    """Povzetek serije za prikaz v seznamu (min/max datum, število)."""
    series_id: str
    prostor: str
    count: int
    min_date: date
    max_date: date


# ── Ocenjevanja ─────────────────────────────────────────────────────

class AssessmentCreate(BaseModel):
    """Vhodni podatki za napoved ocenjevanja.
    
    ponavljanje označuje, ali gre za ocenjevanje ponavljanja (snov iz
    prejšnjih ur) — vpliva na tedenske omejitve.
    """
    razred: str
    date: date
    ponavljanje: bool = False
    teacher_id: int


class AssessmentOut(BaseModel):
    """Izhodni podatki za ocenjevanje."""
    id: int
    razred: str
    date: date
    ponavljanje: bool
    teacher_id: int
    teacher_name: Optional[str] = None  # filled by query join

    model_config = {"from_attributes": True}


# ── Uporabniki ───────────────────────────────────────────────────

class UserOut(BaseModel):
    """Izhodni podatki za uporabnika.
    
    full_name je opcijski — zapolni se v routerju, če je na voljo.
    """
    id: int
    username: str
    email: Optional[str] = None
    first_name: str
    last_name: str
    role: str
    is_active: bool
    full_name: Optional[str] = None

    model_config = {"from_attributes": True}
