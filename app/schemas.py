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

    model_config = {"from_attributes": True}


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
