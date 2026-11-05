# Strežniški timeout neaktivnosti — velja na VSAKI prijavljeni strani.
import time as _time

from app.security import session_inactivity_check, sign_user_id
from tests.conftest import login


def _stari_cookie(uid: int, starejsa_za: float) -> str:
    """Podpiši user_id cookie s časom, pomaknjenim za `starejsa_za` sekund nazaj."""
    orig = _time.time
    try:
        _time.time = lambda: orig() - starejsa_za
        return sign_user_id(uid)
    finally:
        _time.time = orig


def test_fresh_session_ostane_prijavljen(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    r = client.get("/auth/me", follow_redirects=False)
    assert r.status_code == 200, r.status_code
    assert r.json().get("id") == admin.id


def test_stara_seja_se_samodejno_odjavi(client, make_user):
    """Cookie starejši od timeouta (npr. odprt zavihek čez noč) → preusmeritev."""
    admin = make_user(role="admin")
    login(client, admin.username)
    client.cookies.set("user_id", _stari_cookie(admin.id, starejsa_za=2 * 3600))
    r = client.get("/rezervacije", follow_redirects=False)
    assert r.status_code == 303, r.status_code
    assert r.headers.get("location", "").startswith("/auth/login")


def test_stara_seja_api_401(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    client.cookies.set("user_id", _stari_cookie(admin.id, starejsa_za=2 * 3600))
    r = client.get("/api/schools/current", follow_redirects=False)
    assert r.status_code == 401, (r.status_code, r.text[:150])


def test_govorilne_ure_ima_timeout_js(client, make_user):
    """/govorilne/ure sedaj pošlje INACTIVITY_TIMEOUT + JS timer (kot ostale strani)."""
    admin = make_user(role="admin")
    login(client, admin.username)
    r = client.get("/govorilne/ure", follow_redirects=False)
    assert r.status_code == 200, r.status_code
    assert "const t=" in r.text
    assert "/auth/logout" in r.text


def test_session_inactivity_check_klicalnik():
    """Enotski test odločanja: ok / refresh / expired glede na starost cookieja."""
    uid = 1
    c = sign_user_id(uid)
    now = _time.time()
    assert session_inactivity_check(uid, c, 1200, now=now) == "ok"
    assert session_inactivity_check(uid, c, 1200, now=now + 100) == "refresh"
    assert session_inactivity_check(uid, c, 1200, now=now + 2000) == "expired"
    assert session_inactivity_check(uid, None, 1200) == "ok"          # brez cookieja
    assert session_inactivity_check(uid, c, 0, now=now + 2000) == "ok"  # izklopljeno