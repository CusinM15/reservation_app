# ─────────────────────────────────────────────────────────────────────────
# tests/conftest.py — Skupne nastavitve in fixtureji za pytest
#
# Namen: Nastavi okoljske spremenljivke PRED importom aplikacije
# (config.py se izvede ob importu), pripravi TestClient in pomožne
# fixtureje za ustvarjanje uporabnikov ter čiščenje baze med testi.
#
# Zakaj PostgreSQL? Produkcija je 100% PostgreSQL (config.py zahteva
# DATABASE_URL in SQLite ni podprt). Testi morajo teči na isti bazi
# kot produkcija.
# ─────────────────────────────────────────────────────────────────────────

import os
from uuid import uuid4

# ⚠️ Env MORA biti nastavljen PRED importom app.* (config.py se izvede ob
# importu in fail-fast-a brez DATABASE_URL).
os.environ.setdefault("DATABASE_URL", "postgresql://postgres@localhost:5432/testdb")
os.environ.setdefault("PROSTORI", "tablice,racunalnica,ladja,gospodinjska-ucilnica")
os.environ.setdefault(
    "RAZREDI",
    "1.a,1.b,1.c,1.č,2.a,2.b,2.c,2.č,3.a,3.b,3.c,3.č,4.a,4.b,4.c,4.č,"
    "5.a,5.b,5.c,5.č,6.a,6.b,6.c,6.č,7.a,7.b,7.c,8.a,8.b,8.c,8.č,9.a,9.b,9.c,9.č",
)
os.environ.setdefault(
    "SCHEDULE",
    '{"0":"7.00 - 7.45","1":"7.50 - 8.35","2":"8.40 - 9.25","3":"9.30 - 10.15",'
    '"4":"10.25 - 11.10","5":"11.15 - 12.00","6":"12.05 - 12.50","7":"12.55 - 13.40"}',
)
os.environ.setdefault("TABLICE_MAX", "28")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("MAIL_PASSWORD", "")  # _send_email je best-effort — brez gesla ne pošilja

import pytest
from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import text

from app.main import app
from app.database import SessionLocal
from app.models import User, RoleEnum

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TEST_PASSWORD = "Test12345"  # ustreza validate_password_strength


@pytest.fixture
def client():
    """Svež TestClient na testno bazo (startup zažene init_db + bootstrap admina)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db():
    """Po vsakem testu počisti VSE tabele (tudi users) — testi so hermetični,
    bootstrap admina se ob startupu vsakega TestClient-a znova ustvari."""
    yield
    db = SessionLocal()
    try:
        db.execute(text("TRUNCATE users, reservations, assessments, audit_log, blocked_dates RESTART IDENTITY CASCADE"))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def make_user():
    """Ustvari uporabnika z znanim geslom in vrne User objekt."""
    def _make(role: str = "teacher", username: str | None = None, email: str | None = None,
              password: str = TEST_PASSWORD) -> User:
        suffix = uuid4().hex[:8]
        db = SessionLocal()
        try:
            user = User(
                username=username or f"{role}_{suffix}",
                email=email or f"{suffix}@test.si",
                first_name="Test",
                last_name=role.capitalize(),
                password_hash=pwd_context.hash(password),
                role=RoleEnum(role),
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
        finally:
            db.close()
    return _make


def login(client: TestClient, username: str, password: str = TEST_PASSWORD):
    """Prijava prek /auth/login — piškotki ostanejo v client cookie jar."""
    return client.post("/auth/login", data={"username": username, "password": password})


def get_user_from_db(user_id: int) -> User:
    """Pomožnik za direktno preverjanje stanja v bazi."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        db.expunge(user) if user else None
        return user
    finally:
        db.close()
