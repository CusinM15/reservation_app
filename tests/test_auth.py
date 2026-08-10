# ─────────────────────────────────────────────────────────────────────────
# tests/test_auth.py — Avtentikacija: prijava, sprememba gesla,
# pozabljeno geslo (celoten flow), varnostne kontrole
# ─────────────────────────────────────────────────────────────────────────

from app.database import SessionLocal
from app.models import User
from app.routers.auth import verify_password
from tests.conftest import login, get_user_from_db

NOVO_GESLO = "NovoGeslo1"  # ustreza validate_password_strength


# ── Prijava ────────────────────────────────────────────────────────────

def test_login_success_username(client, make_user):
    u = make_user()
    r = login(client, u.username)
    assert r.status_code in (200, 303)
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == u.id
    assert me.json()["role"] == "teacher"


def test_login_success_email(client, make_user):
    u = make_user(email="mail@test.si")
    r = login(client, "mail@test.si")
    assert r.status_code in (200, 303)
    assert client.get("/auth/me").json()["id"] == u.id


def test_login_wrong_password(client, make_user):
    u = make_user()
    r = login(client, u.username, password="Napačno1")
    assert r.status_code == 200  # login stran z napako
    assert "Napačno uporabniško ime ali geslo" in r.text
    assert client.get("/auth/me", follow_redirects=False).status_code == 307  # ni prijavljen


def test_me_requires_login(client):
    assert client.get("/auth/me", follow_redirects=False).status_code == 307


# ── Sprememba gesla (prijavljen uporabnik) ─────────────────────────────

def test_change_password(client, make_user):
    u = make_user()
    login(client, u.username)

    r = client.post("/auth/change-password", data={"old_password": "Test12345", "new_password": NOVO_GESLO})
    assert r.status_code == 200, r.text

    # Hash v bazi se je spremenil
    db_user = get_user_from_db(u.id)
    assert verify_password(NOVO_GESLO, db_user.password_hash)
    assert not verify_password("Test12345", db_user.password_hash)


def test_change_password_wrong_old(client, make_user):
    u = make_user()
    login(client, u.username)

    r = client.post("/auth/change-password", data={"old_password": "Napačno1", "new_password": NOVO_GESLO})
    assert r.status_code == 400
    db_user = get_user_from_db(u.id)
    assert verify_password("Test12345", db_user.password_hash)  # geslo nespremenjeno


def test_change_password_weak_new(client, make_user):
    u = make_user()
    login(client, u.username)
    r = client.post("/auth/change-password", data={"old_password": "Test12345", "new_password": "abc"})
    assert r.status_code == 400
    db_user = get_user_from_db(u.id)
    assert verify_password("Test12345", db_user.password_hash)


# ── Pozabljeno geslo (celoten flow) ────────────────────────────────────

def _get_reset_token(user_id: int) -> str:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first().reset_token
    finally:
        db.close()


def test_forgot_password_full_flow(client, make_user):
    u = make_user(email="forgot@test.si")
    email = "forgot@test.si"

    # 1) Zahteva za ponastavitev
    r = client.post("/auth/forgot-password", data={"email": email})
    assert r.status_code == 200
    assert "poslali povezavo" in r.text

    # 2) Token je v bazi
    token = _get_reset_token(u.id)
    assert token, "reset_token ne sme biti prazen"

    # 3) Stran za novo geslo (veljaven token)
    r = client.get(f"/auth/reset-password?token={token}&email={email}")
    assert r.status_code == 200
    assert "show_reset" in r.text or "Novo geslo" in r.text

    # 4) Nastavi novo geslo
    r = client.post("/auth/reset-password", data={
        "token": token, "email": email,
        "new_password": NOVO_GESLO, "confirm_password": NOVO_GESLO,
    })
    assert r.status_code == 200
    assert "uspešno spremenjeno" in r.text

    # 5) Prijava z novim geslom deluje, staro ne
    r = login(client, email, password=NOVO_GESLO)
    assert client.get("/auth/me").json()["id"] == u.id
    client.post("/auth/logout")
    r = login(client, email, password="Test12345")
    assert "Napačno" in r.text


def test_forgot_password_unknown_email(client):
    r = client.post("/auth/forgot-password", data={"email": "ni.obstojeci@test.si"})
    assert r.status_code == 200
    assert "ne obstaja" in r.text


def test_reset_password_mismatch(client, make_user):
    u = make_user(email="mismatch@test.si")
    client.post("/auth/forgot-password", data={"email": "mismatch@test.si"})
    token = _get_reset_token(u.id)
    r = client.post("/auth/reset-password", data={
        "token": token, "email": "mismatch@test.si",
        "new_password": NOVO_GESLO, "confirm_password": "DrugGreslo1",
    })
    assert r.status_code == 200
    assert "Gesli se ne ujemata" in r.text
    # geslo nespremenjeno
    assert verify_password("Test12345", get_user_from_db(u.id).password_hash)


def test_reset_password_weak(client, make_user):
    u = make_user(email="weak@test.si")
    client.post("/auth/forgot-password", data={"email": "weak@test.si"})
    token = _get_reset_token(u.id)
    r = client.post("/auth/reset-password", data={
        "token": token, "email": "weak@test.si",
        "new_password": "abc", "confirm_password": "abc",
    })
    assert r.status_code == 200
    assert "Geslo mora" in r.text


def test_reset_token_one_time(client, make_user):
    """Po uspešni ponastavitvi je token pobrisan — drugi poskus pade."""
    u = make_user(email="onetime@test.si")
    client.post("/auth/forgot-password", data={"email": "onetime@test.si"})
    token = _get_reset_token(u.id)

    client.post("/auth/reset-password", data={
        "token": token, "email": "onetime@test.si",
        "new_password": NOVO_GESLO, "confirm_password": NOVO_GESLO,
    })
    assert _get_reset_token(u.id) is None

    r = client.post("/auth/reset-password", data={
        "token": token, "email": "onetime@test.si",
        "new_password": "ŠeEnoGeslo1", "confirm_password": "ŠeEnoGeslo1",
    })
    assert r.status_code == 200
    assert "Neveljavna ali potekla" in r.text
