"""Skupne pytest nastavitve za Šolski App.

Testi uporabljajo IZKLJUČNO PostgreSQL — enako kot produkcija.
SQLite v testih NI podprt (tako kot ni v produkciji)!

TEST_DATABASE_URL mora kazati na PostgreSQL bazo, npr.:
    postgresql://postgres:postgres@localhost:5432/sola_test

Lokalni zagon z Dockerjem:
    docker run -d --name sola-test-db -e POSTGRES_PASSWORD=postgres \
        -e POSTGRES_DB=sola_test -p 5432:5432 postgres:16
    TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sola_test \
        pytest tests/

DATABASE_URL mora biti nastavljen PRED importom app modulov — zato se
nastavi kar tukaj, na vrhu conftest.py.
"""
import os

_db_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
if not _db_url:
    raise RuntimeError(
        "TEST_DATABASE_URL ni nastavljen! Testi uporabljajo izključno PostgreSQL. "
        "Primer: TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sola_test pytest tests/"
    )
if not _db_url.startswith("postgresql"):
    raise RuntimeError(
        f"TEST_DATABASE_URL mora biti PostgreSQL (dobil: {_db_url[:40]}...). "
        "SQLite v testih ni podprt!"
    )
os.environ["DATABASE_URL"] = _db_url

import secrets

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import AuditLog, Reservation, Assessment, BlockedDate, User
from passlib.context import CryptContext

# Hash za admin geslo — izračunan enkrat, da clean_db ne hashira vsakič
ADMIN_HASH = CryptContext(schemes=["bcrypt"], deprecated="auto").hash("admin123")

PASSWORD = "Testiranje2026"


# ── Enkratna priprava: zaženi app (startup -> tabele + admin) ─────────
@pytest.fixture(scope="session")
def app_ready():
    with TestClient(app) as c:
        yield c


# ── Čiščenje med testi (uporabniki ostanejo — admin in test učitelji) ─
@pytest.fixture(autouse=True)
def clean_db(app_ready):
    yield
    db = SessionLocal()
    try:
        db.query(AuditLog).delete()
        db.query(Reservation).delete()
        db.query(Assessment).delete()
        db.query(BlockedDate).delete()
        # Ponastavi admin geslo (testi za menjavo gesla ga lahko spremenijo)
        admin = db.query(User).filter(User.username == "admin").first()
        if admin:
            admin.password_hash = ADMIN_HASH
        db.commit()
    finally:
        db.close()


# ── Pomožne funkcije ───────────────────────────────────────────────────
def create_user(client, username=None, email=None, password=PASSWORD, role="teacher"):
    """Ustvari uporabnika preko admin API-ja. Vrne username.

    Če client še ni prijavljen kot admin, se najprej prijavi (admin/admin123).
    """
    if not client.cookies.get("user_id"):
        login(client, "admin", "admin123")
    uname = username or f"test_{secrets.token_hex(4)}"
    r = client.post("/auth/admin/users", data={
        "username": uname,
        "email": email or f"{uname}@test.si",
        "first_name": "Test",
        "last_name": "Uporabnik",
        "password": password,
        "role": role,
    }, follow_redirects=False)
    assert r.status_code == 303, f"Ustvarjanje uporabnika {uname} ni uspelo: {r.status_code}"
    return uname


def login(client, username, password=PASSWORD):
    """Prijavi uporabnika. Vrne True ob uspehu."""
    r = client.post("/auth/login", data={"username": username, "password": password}, follow_redirects=False)
    assert r.status_code == 303, f"Prijava {username} ni uspela: {r.status_code}"
    return True


def make_client():
    """Svež TestClient z lastnim piškotkovnim sejom."""
    return TestClient(app)


def get_user_id(username):
    """Vrni ID uporabnika iz baze."""
    db = SessionLocal()
    try:
        from app.models import User
        return db.query(User).filter(User.username == username).first().id
    finally:
        db.close()


@pytest.fixture()
def admin_client(app_ready):
    c = make_client()
    login(c, "admin", "admin123")
    yield c
    c.close()


@pytest.fixture()
def teacher_client(app_ready):
    c = make_client()
    uname = create_user(c)   # notranja admin prijava + ustvarjanje
    c.get("/auth/logout")
    login(c, uname)
    yield c
    c.close()
