"""Reprodukcija buga: tedenska serija tablic ne izbriše obstoječe rezervacije.

Scenarij: obstaja rezervacija tablic qty=10 za 10.8.2026 1. uro.
Admin ustvari tedensko serijo tablic qty=28 za isti termin.
Pričakovano: stara rezervacija se pobriše (email lastniku), nova serija qty=28.
Dejansko (bug): stara ostane → skupaj 38 tablic > TABLICE_MAX(28).
"""
import os, sys
REPO = r"C:\Matej\GitHub\reservation_app"
os.chdir(REPO)
sys.path.insert(0, REPO)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date

from app.models import Base, User, Reservation, RoleEnum
from app.config import settings
import app.routers.rezervacije as rz

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
db = sessionmaker(bind=engine)()

admin = User(username="admin", first_name="Admin", last_name="OŠ",
             email="admin@ostc.si", role=RoleEnum.admin, password_hash="x")
db.add(admin)
db.flush()

old = Reservation(prostor="tablice", date=date(2026, 8, 10), hour=0,
                  teacher_id=admin.id, qty=10)
db.add(old)
db.commit()

rz._send_email = lambda **kw: None

res = rz._commit_series(
    db, [(date(2026, 8, 10), 0)],
    prostor="tablice", teacher_id=admin.id,
    creator_name="Admin OŠ", creator_id=admin.id, qty=28,
)
print("Series result:", res)

rows = db.query(Reservation).filter(
    Reservation.prostor == "tablice",
    Reservation.date == date(2026, 8, 10),
    Reservation.hour == 0,
).all()
total = sum(r.qty or 0 for r in rows)
print(f"\nRezervacij v DB: {len(rows)} | skupaj qty: {total} | TABLICE_MAX: {settings.TABLICE_MAX}")
for r in rows:
    print(f"  id={r.id} qty={r.qty} series_id={r.series_id}")

if total > settings.TABLICE_MAX:
    print("\n❌ BUG: kapaciteta presežena — stara rezervacija NI bila izbrisana iz baze")
    sys.exit(1)
else:
    print("\n✅ OK: kapaciteta v redu, konfliktna rezervacija je bila izbrisana")
    sys.exit(0)
