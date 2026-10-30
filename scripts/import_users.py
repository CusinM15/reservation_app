"""Import users from uporabniki.csv into the database.
Usage: python -m scripts.import_users

CSV format: email,ime,priimek[,vloga]
Email is also the username — you write it only once.
Vloga (optional): teacher, vodstvo, admin (default: teacher).
The password is always generated and never printed; users reset it via "Forgot password".
"""

import csv
import secrets
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal, init_db
from app.models import User, RoleEnum
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Users that should be vodstvo
VODSTVO_EMAILS = {
    "gaber.klinar@guest.arnes.si",
    "mateja.cuznar@guest.arnes.si",
    "sanela.hajdarovic@guest.arnes.si",
    "matej.cusin2@guest.arnes.si",
}

_VLOGA_ALIASES = {
    "teacher": RoleEnum.teacher, "ucitelj": RoleEnum.teacher, "profesor": RoleEnum.teacher,
    "professor": RoleEnum.teacher,
    "vodstvo": RoleEnum.vodstvo, "vodja": RoleEnum.vodstvo, "ravnatelj": RoleEnum.vodstvo,
    "admin": RoleEnum.admin, "administrator": RoleEnum.admin, "skrbnik": RoleEnum.admin,
}


def _generate_password(length: int = 12) -> str:
    """Naključno geslo (mala+velika+številka), ki ustreza pravilom šole.

    Nikoli se ne izpiše — uporabnik si ga nastavi sam prek »Pozabljeno geslo«.
    """
    lower = "abcdefghijkmnopqrstuvwxyz"
    upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    alphabet = lower + upper + digits
    chars = [secrets.choice(lower), secrets.choice(upper), secrets.choice(digits)]
    chars += [secrets.choice(alphabet) for _ in range(max(0, length - 3))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def run():
    init_db()
    db = SessionLocal()

    csv_path = os.path.join(os.path.dirname(__file__), "..", "uporabniki.csv")
    imported = 0
    skipped = 0
    errors = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if not any((cell or "").strip() for cell in row):
                continue
            cells = (row + [""] * 4)[:4]
            email, first_name, last_name, vloga = (c.strip() for c in cells)
            if not email:
                errors.append("vrstica z manjkajočo e-pošto (e-pošta je tudi uporabniško ime)")
                continue

            existing = db.query(User).filter(User.username == email).first()
            if existing:
                # Vodstvo za že uvožene uporabnike (določeno po e-pošti).
                if email in VODSTVO_EMAILS:
                    existing.role = RoleEnum.vodstvo
                skipped += 1
                continue

            if vloga:
                role = _VLOGA_ALIASES.get(vloga.lower())
                if role is None:
                    errors.append(f"{email}: neveljavna vloga '{vloga}' (dovoljeno: učitelj, vodstvo, admin)")
                    continue
            else:
                # Privzeta vloga: vodstvo (določeno po e-pošti) ali učitelj.
                role = RoleEnum.vodstvo if email in VODSTVO_EMAILS else RoleEnum.teacher

            user = User(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password_hash=pwd_context.hash(_generate_password()),
                role=role,
                is_active=True,
                ima_govorilne=False,   # privzeto uporabnik NIMA govorilnih ur
            )
            db.add(user)
            imported += 1
            print(f"  Imported {email} ({first_name} {last_name}) [{role.value}]")

    db.commit()
    db.close()

    print(f"\nDone: {imported} imported, {skipped} skipped")
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    run()
