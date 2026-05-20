from datetime import date

from sqlalchemy import Boolean, Column, Integer, String, Date, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class RoleEnum(str, enum.Enum):
    admin = "admin"
    teacher = "teacher"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(SAEnum(RoleEnum), default=RoleEnum.teacher, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    reservations = relationship("Reservation", back_populates="teacher")
    assessments = relationship("Assessment", back_populates="teacher")


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    prostor = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    hour = Column(Integer, nullable=False)  # 0–7
    razred = Column(String, nullable=False)
    qty = Column(Integer, nullable=True)  # only for tablice

    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    teacher = relationship("User", back_populates="reservations")


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    razred = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    ponavljanje = Column(Boolean, default=False, nullable=False)

    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    teacher = relationship("User", back_populates="assessments")
