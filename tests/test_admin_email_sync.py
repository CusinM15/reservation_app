# ─────────────────────────────────────────────────────────────────────────
# tests/test_admin_email_sync.py — e-pošta šolskega admina je vezana na nastavitve
#
# Zahteva uporabnika (2026-09-23): »admin_ostcj mora imeti tisti e-naslov, ki je
# določen v nastavitvah, in drugače ga sploh ne moreš spremeniti kakor skozi
# nastavitve.«
#
# Torej:
#   * ob shranjevanju nastavitve ADMIN_EMAIL se e-pošta GLAVNEGA (najstarejšega)
#     admin računa te šole samodejno uskladi (nastavitev → račun),
#   * admin računu e-pošte NI mogoče spremeniti prek obrazca za urejanje
#     uporabnika (ostane vrednost iz nastavitev),
#   * nov/uvoz admin račun dobi e-pošto iz nastavitev, če je naslov prost,
#   * če naslov že uporablja drug uporabnik iste šole (UNIQUE school_id+email),
#     shranjevanje vrne JASNO napako namesto tihega neuspeha.
# ─────────────────────────────────────────────────────────────────────────

from uuid import uuid4

from app.database import SessionLocal
from app.models import User
from app.tenancy import apply_admin_email, primary_admin, sync_admin_user_email
from tests.conftest import default_school_id, login


def _fresh_email(prefix: str = "admin"):
    """Unikaten naslov za vsak test — testna baza se med testi NE prazni, zato
    fiksni naslovi trčijo na UNIQUE (school_id, email)."""
    return f"{prefix}.{uuid4().hex[:8]}@guest.arnes.si"


def _admin(client, make_user):
    admin = make_user(role="admin")
    login(client, admin.username)
    return admin


def _set_admin_email(client, sid, value):
    return client.put(f"/api/schools/{sid}/settings", json={"values": {"ADMIN_EMAIL": value}})


def _db_user(user_id):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


def _primary_admin_id(sid):
    db = SessionLocal()
    try:
        return primary_admin(db, sid).id
    finally:
        db.close()


# ── 1. Nastavitev → glavni admin račun ────────────────────────────────

def test_settings_update_syncs_admin_user_email(client, make_user):
    _admin(client, make_user)
    sid = default_school_id()
    email = _fresh_email()

    r = _set_admin_email(client, sid, email)
    assert r.status_code == 200, r.text

    primary_id = _primary_admin_id(sid)
    assert _db_user(primary_id).email == email


def test_sync_does_not_touch_teachers(client, make_user):
    _admin(client, make_user)
    teacher = make_user()
    sid = default_school_id()
    email = _fresh_email()

    assert _set_admin_email(client, sid, email).status_code == 200
    assert _db_user(teacher.id).email != email


def test_sync_helper_reports_changes(client, make_user):
    _admin(client, make_user)
    sid = default_school_id()
    email = _fresh_email()
    db = SessionLocal()
    try:
        # počistimo naslov glavnega admina, da sync najde spremembo
        db.query(User).filter(User.id == _primary_admin_id(sid)).update({"email": None})
        db.commit()

        changes, conflict = sync_admin_user_email(db, sid, email)
        assert conflict is None
        assert any(email in c for c in changes)
        # ko spremembo zapišemo (apply), sync ne najde več razlike (idempotentno)
        apply_admin_email(db, sid, email)
        db.flush()
        assert sync_admin_user_email(db, sid, email) == ([], None)
        db.rollback()
    finally:
        db.close()


# ── 2. Konflikt: naslov že uporablja drug račun ──────────────────────

def test_conflicting_email_is_refused_with_clear_message(client, make_user):
    """Uporabnik je prav to doživel v produkciji ('zavrnilo stran') — zdaj dobi
    jasno razlago, nastavitev pa se NE shrani na pol."""
    _admin(client, make_user)
    teacher = make_user()
    sid = default_school_id()
    email = _fresh_email("zasedeno")

    db = SessionLocal()
    try:
        db.query(User).filter(User.id == teacher.id).update({"email": email})
        db.commit()
    finally:
        db.close()

    r = _set_admin_email(client, sid, email)
    assert r.status_code == 400
    assert "že uporablja" in r.json()["detail"]

    # nastavitev ni bila shranjena (transakcija je bila razveljavljena)
    from app.tenancy import get_school_config
    db = SessionLocal()
    try:
        assert get_school_config(db, sid).ADMIN_EMAIL != email
    finally:
        db.close()


# ── 3. Uporabniški obrazec NE more spremeniti e-pošte admina ──────────

def test_update_user_cannot_change_admin_email(client, make_user):
    """Naslov admina nosi glavni admin račun šole; prek obrazca za urejanje
    uporabnika ga NIKAKOR ni mogoče spremeniti (samo prek /settings)."""
    _admin(client, make_user)                    # samo da smo prijavljeni kot admin
    sid = default_school_id()
    email = _fresh_email("glavni")
    assert _set_admin_email(client, sid, email).status_code == 200

    primary_id = _primary_admin_id(sid)
    assert _db_user(primary_id).email == email

    r = client.post(f"/auth/admin/users/{primary_id}/update", data={
        "username": _db_user(primary_id).username,
        "email": _fresh_email("poskus"),         # poskus mimo nastavitev
        "first_name": "Test",
        "last_name": "Admin",
        "role": "admin",
    })
    assert r.status_code in (200, 303), r.text
    assert _db_user(primary_id).email == email, "e-pošta admina se NE sme spremeniti tu"


def test_update_user_can_still_change_teacher_email(client, make_user):
    admin = _admin(client, make_user)
    teacher = make_user()

    r = client.post(f"/auth/admin/users/{teacher.id}/update", data={
        "username": teacher.username,
        "email": "ucitelj.novi@test.si",
        "first_name": "Učitelj",
        "last_name": "Testni",
        "role": "teacher",
    })
    assert r.status_code in (200, 303), r.text
    assert _db_user(teacher.id).email == "ucitelj.novi@test.si"


# ── 4. Nov / uvožen admin račun ───────────────────────────────────────

def test_create_admin_user_takes_email_from_settings(client, make_user):
    _admin(client, make_user)
    sid = default_school_id()
    email = _fresh_email("glavni")
    assert _set_admin_email(client, sid, email).status_code == 200

    r = client.post("/auth/admin/users", data={
        "username": f"novi.admin.{uuid4().hex[:6]}@test.si",
        "email": "izmisli.si@test.si",          # se IGNORIRA (naslov je zaseden)
        "first_name": "Novi",
        "last_name": "Admin",
        "password": "Geslo123",
        "role": "admin",
    })
    assert r.status_code in (200, 303), r.text

    db = SessionLocal()
    try:
        u = (db.query(User)
               .filter(User.school_id == sid, User.first_name == "Novi",
                       User.last_name == "Admin")
               .order_by(User.id.desc()).first())
        assert u is not None and u.role == "admin"
        # Naslov iz nastavitev zaseda glavni admin, zato novi admin ostane brez
        # e-pošte (namesto da bi shranjevanje padlo na UNIQUE omejitvi).
        assert u.email is None
    finally:
        db.close()


def test_csv_import_admin_role_uses_settings_email_when_free(client, make_user):
    _admin(client, make_user)
    sid = default_school_id()
    email = _fresh_email("uvoz")
    assert _set_admin_email(client, sid, email).status_code == 200

    # sprostimo naslov (glavni admin ga ima) — nato naj ga dobi uvoženi admin
    db = SessionLocal()
    try:
        db.query(User).filter(User.id == _primary_admin_id(sid)).update({"email": None})
        db.commit()
    finally:
        db.close()

    uname = f"uvoz.admin.{uuid4().hex[:6]}@test.si"
    csv_text = f"uporabnisko_ime,email,ime,priimek,vloga\n{uname},nekaj@test.si,Uvoz,Admin,admin\n"
    r = client.post("/auth/admin/users/import",
                    files={"file": ("u.csv", csv_text, "text/csv")})
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == uname, User.school_id == sid).first()
        assert u is not None and u.role == "admin"
        assert u.email == email
    finally:
        db.close()


# ── 5. UI: polje je za admina samo za branje ─────────────────────────

def test_admin_users_page_marks_admin_email_readonly(client, make_user):
    _admin(client, make_user)
    html = client.get("/auth/admin/users").text
    assert "readonly" in html
    assert "Vezano na /settings" in html
