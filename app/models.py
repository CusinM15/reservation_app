from datetime import date, datetime

from sqlalchemy import Boolean, Column, Integer, String, Date, DateTime, Text, ForeignKey, Enum as SAEnum, BigInteger
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class RoleEnum(str, enum.Enum):
    admin = "admin"
    vodstvo = "vodstvo"
    teacher = "teacher"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    first_name = Column(String, nullable=False, default="")
    last_name = Column(String, nullable=False, default="")
    password_hash = Column(String, nullable=False)
    role = Column(SAEnum(RoleEnum), default=RoleEnum.teacher, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    reset_token = Column(String, nullable=True, default=None, index=True)

    reservations = relationship("Reservation", back_populates="teacher")
    assessments = relationship("Assessment", back_populates="teacher")


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    prostor = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    hour = Column(Integer, nullable=False)  # 0–7
    razred = Column(String, nullable=True, default="")
    qty = Column(Integer, nullable=True)  # only for tablice

    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    teacher = relationship("User", back_populates="reservations")

    # Identifier of a recurring/full-day series. NULL = enkratna rezervacija.
    # Vsi zapisi iste serije (npr. "vsak četrtek predura računalnica" ali
    # "naravoslovni dan: vse ure istega dne") delijo isti series_id.
    series_id = Column(String, nullable=True, index=True)


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    razred = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    ponavljanje = Column(Boolean, default=False, nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    teacher = relationship("User", back_populates="assessments")


class BlockedDate(Base):
    __tablename__ = "blocked_dates"

    id = Column(Integer, primary_key=True, index=True)
    razred = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_by = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    username = Column(String, nullable=True)
    action = Column(String, nullable=False, index=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User")
