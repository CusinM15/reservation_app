"""Import users from uporabniki.csv into the database.
Usage: python -m scripts.import_users

CSV format: uporabnisko_ime,geslo,ime,priimek,email[,vloga]
If vloga column is present, values: teacher, vodstvo, admin
"""

import csv, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal, init_db
from app.models import User, RoleEnum
from app.config import validate_password_strength
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Users that should be vodstvo
VODSTVO_EMAILS = {
    "gaber.klinar@guest.arnes.si",
    "mateja.cuznar@guest.arnes.si",
    "sanela.hajdarovic@guest.arnes.si",
    "matej.cusin2@guest.arnes.si",
}


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
            username, password, first_name, last_name, email = row[:5]

            existing = db.query(User).filter(User.username == username).first()
            if existing:
                # Update password hash if it's not already bcrypt
                if not existing.password_hash.startswith("$2b$") and not existing.password_hash.startswith("$2a$"):
                    existing.password_hash = pwd_context.hash(password)
                # Set vodstvo role for designated users
                if username in VODSTVO_EMAILS:
                    existing.role = RoleEnum.vodstvo
                skipped += 1
                continue

            # Validate password
            err = validate_password_strength(password)
            if err:
                errors.append(f"{username}: {err}")
                continue

            # Determine role
            role = RoleEnum.vodstvo if username in VODSTVO_EMAILS else RoleEnum.teacher

            user = User(
                username=username,
                email=email or None,
                first_name=first_name,
                last_name=last_name,
                password_hash=pwd_context.hash(password),
                role=role,
                is_active=True,
            )
            db.add(user)
            imported += 1
            print(f"  Imported {username} ({first_name} {last_name}) [{role.value}]")

    db.commit()
    db.close()

    print(f"\nDone: {imported} imported, {skipped} skipped")
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    run()
