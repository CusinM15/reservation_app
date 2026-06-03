from pydantic import BaseModel, Field
from datetime import date
from typing import Optional


# ── Reservations ─────────────────────────────────────────────

class ReservationCreate(BaseModel):
    date: date
    hour: int = Field(..., ge=0, le=7)
    prostor: str
    razred: Optional[str] = None
    teacher_id: int
    qty: Optional[int] = None


class ReservationOut(BaseModel):
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


# ── Serijske rezervacije (samo admin/vodstvo) ──────────────────

class WeeklySeriesCreate(BaseModel):
    """Rezerviraj isto uro vsak teden na isti dan v tednu, med date_from in date_to (vključno). Samo admin/vodstvo."""
    prostor: str
    hour: int = Field(..., ge=0, le=7)
    weekday: int = Field(..., ge=0, le=6, description="0=ponedeljek ... 6=nedelja (Python weekday())")
    date_from: date
    date_to: date
    qty: Optional[int] = None


class FullDaySeriesCreate(BaseModel):
    """Rezerviraj vse ure (0–7) za en ali več dni (npr. naravoslovni dan). Samo admin/vodstvo."""
    prostor: str
    date_from: date
    date_to: date  # za en sam dan: date_from == date_to
    qty: Optional[int] = None
    hours: Optional[list[int]] = Field(
        default=None,
        description="Privzeto vse ure 0..7. Lahko se omeji npr. na [0,1,2,3,4,5] za 6 ur.",
    )


class SeriesResult(BaseModel):
    series_id: str
    created: int
    skipped: list[dict] = Field(default_factory=list)  # [{date, hour, reason}]
    removed: int = 0  # število pobrisanih konfliktnih rezervacij


# ── Assessments ─────────────────────────────────────────────

class AssessmentCreate(BaseModel):
    razred: str
    date: date
    ponavljanje: bool = False
    teacher_id: int


class AssessmentOut(BaseModel):
    id: int
    razred: str
    date: date
    ponavljanje: bool
    teacher_id: int
    teacher_name: Optional[str] = None  # filled by query join

    model_config = {"from_attributes": True}


# ── Users ──────────────────────────────────────────────

class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    first_name: str
    last_name: str
    role: str
    is_active: bool
    full_name: Optional[str] = None

    model_config = {"from_attributes": True}
