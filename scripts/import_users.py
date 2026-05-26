"""Import users from uporabniki.csv into the database.
Usage: python -m scripts.import_users
"""

import csv, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal, init_db
from app.models import User, RoleEnum
from app.config import validate_password_strength
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
            username, password, first_name, last_name, email = row

            existing = db.query(User).filter(User.username == username).first()
            if existing:
                # Update password if CSV has a new one
                if not existing.password_hash.startswith("$2b$") and not existing.password_hash.startswith("$2a$"):
                    existing.password_hash = pwd_context.hash(password)
                    print(f"  Updated password for {username}")
                skipped += 1
                continue

            # Validate password
            err = validate_password_strength(password)
            if err:
                errors.append(f"{username}: {err}")
                continue

            user = User(
                username=username,
                email=email or None,
                first_name=first_name,
                last_name=last_name,
                password_hash=pwd_context.hash(password),
                role=RoleEnum.teacher,
                is_active=True,
            )
            db.add(user)
            imported += 1
            print(f"  Imported {username} ({first_name} {last_name})")

    db.commit()
    db.close()

    print(f"\nDone: {imported} imported, {skipped} skipped")
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    run()
