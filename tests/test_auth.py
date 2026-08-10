"""Testi za avtentikacijo: prijava, menjava gesla, pozabljeno/ponastavitev gesla."""
import pytest
from conftest import create_user, login, make_client, get_user_id


def _login_response(client, username, password):
    return client.post("/auth/login", data={"username": username, "password": password}, follow_redirects=False)


# ═══ PRIJAVA ═══
def test_login_success(admin_client):
    assert admin_client.cookies.get("user_id")
    assert "admin" in admin_client.cookies.get("role", "")


def test_login_wrong_password(app_ready):
    c = make_client()
    r = _login_response(c, "admin", "napačno_geslo")
    assert r.status_code == 200  # login stran z napako
    assert "Napačno uporabniško ime ali geslo" in r.text
    assert not c.cookies.get("user_id")


def test_login_unknown_user(app_ready):
    c = make_client()
    r = _login_response(c, "neobstaja", "karkoli123")
    assert r.status_code == 200
    assert "Napačno uporabniško ime ali geslo" in r.text


def test_login_rate_limit(admin_client):
    """Po 10 napačnih poskusih je prijava blokirana (brute force zaščita)."""
    c = make_client()
    for i in range(10):
        r = _login_response(c, "rate_limit_user", f"napačno{i}")
        assert "Preveč neuspešnih" not in r.text
    r = _login_response(c, "rate_limit_user", "napačno10")
    assert "Preveč neuspešnih poskusov prijave" in r.text


# ═══ MENJAVA GESLA ═══
def test_change_password_success(admin_client):
    c = admin_client
    r = c.post("/auth/change-password", data={"old_password": "admin123", "new_password": "NovoGeslo123"}, follow_redirects=False)
    assert r.status_code == 200
    assert "uspešno spremenjeno" in r.json()["message"].lower()
    # stara prijava ne deluje več, nova deluje
    c.get("/auth/logout")
    r = _login_response(c, "admin", "admin123")
    assert "Napačno" in r.text
    r = _login_response(c, "admin", "NovoGeslo123")
    assert r.status_code == 303


def test_change_password_wrong_old(admin_client):
    r = admin_client.post("/auth/change-password", data={"old_password": "napačno", "new_password": "NovoGeslo123"})
    assert r.status_code == 400
    assert "Staro geslo ni pravilno" in r.json()["detail"]


def test_change_password_weak_new(admin_client):
    r = admin_client.post("/auth/change-password", data={"old_password": "admin123", "new_password": "abc"})
    assert r.status_code == 400


def test_change_password_unauthorized(app_ready):
    c = make_client()
    r = c.post("/auth/change-password", data={"old_password": "x", "new_password": "y"}, follow_redirects=False)
    assert r.status_code == 307  # preusmeritev na login


# ═══ POZABLJENO GESLO ═══
def test_forgot_password_success(admin_client):
    c = admin_client
    uname = create_user(c, email="pozabljen@test.si")
    r = c.post("/auth/forgot-password", data={"email": "pozabljen@test.si"})
    assert r.status_code == 200
    assert "poslali povezavo" in r.text
    # token je shranjen v bazi
    db_user_id = get_user_id(uname)
    from app.database import SessionLocal
    from app.models import User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == db_user_id).first()
        assert user.reset_token and ":" in user.reset_token
    finally:
        db.close()


def test_forgot_password_unknown_email(admin_client):
    """Varnost: tudi za neobstoječ email se pokaže enako sporočilo (brez email enumeration)."""
    r = admin_client.post("/auth/forgot-password", data={"email": "neobstaja@test.si"})
    assert r.status_code == 200
    assert "poslali povezavo" in r.text
    assert "ne obstaja" not in r.text


# ═══ PONASTAVITEV GESLA ═══
def test_reset_password_full_flow(admin_client):
    c = admin_client
    create_user(c, email="reset@test.si")
    c.post("/auth/forgot-password", data={"email": "reset@test.si"})

    from app.database import SessionLocal
    from app.models import User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "reset@test.si").first()
        token = user.reset_token
    finally:
        db.close()

    # GET stran za ponastavitev (veljaven token)
    r = c.get(f"/auth/reset-password?token={token}&email=reset@test.si")
    assert r.status_code == 200
    assert "reset" in r.text.lower()

    # POST novo geslo
    r = c.post("/auth/reset-password", data={
        "token": token, "email": "reset@test.si",
        "new_password": "NovoGeslo456", "confirm_password": "NovoGeslo456",
    })
    assert r.status_code == 200

    # Prijava z novim geslom deluje
    c2 = make_client()
    assert login(c2, "reset@test.si", "NovoGeslo456")

    # Token je enkraten — drugi poskus ne sme delovati
    r = c.post("/auth/reset-password", data={
        "token": token, "email": "reset@test.si",
        "new_password": "SpetNovo123", "confirm_password": "SpetNovo123",
    })
    assert "Neveljavna ali potekla" in r.text


def test_reset_password_bad_token(admin_client):
    r = admin_client.post("/auth/reset-password", data={
        "token": "fake:123", "email": "kdo@test.si",
        "new_password": "NovoGeslo123", "confirm_password": "NovoGeslo123",
    })
    assert "Neveljavna ali potekla" in r.text


def test_reset_password_mismatch(admin_client):
    create_user(admin_client, email="mismatch@test.si")
    admin_client.post("/auth/forgot-password", data={"email": "mismatch@test.si"})
    from app.database import SessionLocal
    from app.models import User
    db = SessionLocal()
    try:
        token = db.query(User).filter(User.email == "mismatch@test.si").first().reset_token
    finally:
        db.close()
    r = admin_client.post("/auth/reset-password", data={
        "token": token, "email": "mismatch@test.si",
        "new_password": "NovoGeslo123", "confirm_password": "Drugačno123",
    })
    assert "Gesli se ne ujemata" in r.text
